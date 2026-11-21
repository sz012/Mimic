from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import imagehash
from PIL import Image, ImageStat

from engine.schema import Feature, Item

GROUP = "visual"
MIN_SIDE = 80
MAX_ASSETS = 150
VIDEO_STEP_SECONDS = 2
MAX_IMAGE_BYTES = 15_000_000
ASSET_DIR_SUFFIX = "_files"
ASSET_DIR_NAMES = ("resources",)

Image.MAX_IMAGE_PIXELS = 60_000_000


def _open(data: bytes) -> Image.Image | None:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None
    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def _is_informative(img: Image.Image) -> bool:
    if min(img.size) < MIN_SIDE:
        return False
    stat = ImageStat.Stat(img.convert("L").resize((64, 64)))
    return stat.stddev[0] > 6


def image_hashes(img: Image.Image) -> dict[str, str]:
    return {"phash": str(imagehash.phash(img)), "dhash": str(imagehash.dhash(img))}


def _screenshot_entries(item: Item, raw_dir: Path) -> list[dict]:
    out = []
    for rel in item.paths.get("screenshot", []):
        path = raw_dir / rel
        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                continue
            img = _open(path.read_bytes())
        except OSError:
            continue
        if img is None:
            continue
        top = img.crop((0, 0, img.width, min(img.height, img.width)))
        out.append(
            {
                "src": rel,
                "w": img.width,
                "h": img.height,
                **image_hashes(img),
                "top_phash": str(imagehash.phash(top)),
            }
        )
    return out


def _asset_dirs(item: Item, raw_dir: Path) -> list[Path]:
    dirs = []
    for rel in item.paths.get("html", []):
        html = raw_dir / rel
        cand = html.with_name(html.stem + ASSET_DIR_SUFFIX)
        if cand.is_dir():
            dirs.append(cand)
        for name in ASSET_DIR_NAMES:
            res = html.parent / name
            if res.is_dir():
                dirs.append(res)
    return list(dict.fromkeys(dirs))


def _asset_entries_from_dirs(dirs: list[Path], raw_dir: Path) -> list[dict]:
    out, seen = [], set()
    for d in dirs:
        for path in sorted(p for p in d.rglob("*") if p.is_file()):
            if len(out) >= MAX_ASSETS:
                return out
            if path.suffix.lower() in (".css", ".js", ".html", ".htm", ".svg", ".json", ".txt"):
                continue
            try:
                if path.stat().st_size > MAX_IMAGE_BYTES:
                    continue
                img = _open(path.read_bytes())
            except OSError:
                continue
            if img is None or not _is_informative(img):
                continue
            h = str(imagehash.phash(img))
            if h in seen:
                continue
            seen.add(h)
            out.append(
                {"src": str(path.relative_to(raw_dir)), "w": img.width, "h": img.height, "phash": h}
            )
    return out


def _asset_entries_from_har(item: Item, raw_dir: Path) -> list[dict]:
    out, seen = [], set()
    for rel in item.paths.get("har", []):
        try:
            har = json.loads((raw_dir / rel).read_bytes())
        except (OSError, ValueError):
            continue
        for entry in har.get("log", {}).get("entries", []):
            if len(out) >= MAX_ASSETS:
                return out
            content = entry.get("response", {}).get("content", {})
            if not (content.get("mimeType") or "").startswith("image/") or "svg" in content.get(
                "mimeType", ""
            ):
                continue
            text = content.get("text")
            if not text:
                continue
            try:
                data = (
                    base64.b64decode(text)
                    if content.get("encoding") == "base64"
                    else text.encode("latin-1")
                )
            except (ValueError, UnicodeEncodeError):
                continue
            img = _open(data)
            if img is None or not _is_informative(img):
                continue
            h = str(imagehash.phash(img))
            if h in seen:
                continue
            seen.add(h)
            url = entry.get("request", {}).get("url", "")
            out.append({"src": f"{rel}:{url[:160]}", "w": img.width, "h": img.height, "phash": h})
    return out


def extract(item: Item, raw_dir: Path) -> dict[str, Feature]:
    raw_dir = Path(raw_dir)
    feats: dict[str, Feature] = {}
    shots = _screenshot_entries(item, raw_dir)
    feats["visual.screenshot"] = (
        Feature("visual.screenshot", GROUP, shots, 0.8, "zrzuty ekranu: pHash/dHash")
        if shots
        else Feature.missing("visual.screenshot", GROUP, "brak zrzutów ekranu")
    )
    dirs = _asset_dirs(item, raw_dir)
    assets = _asset_entries_from_dirs(dirs, raw_dir)
    source = "zasoby strony (_files/resources)"
    if not assets:
        assets = _asset_entries_from_har(item, raw_dir)
        source = "obrazy z odpowiedzi HAR"
    feats["visual.assets"] = (
        Feature(
            "visual.assets", GROUP, assets, round(min(1.0, len(assets) / 5), 3), f"{source}: pHash"
        )
        if assets
        else Feature.missing("visual.assets", GROUP, "brak obrazów w zasobach strony i HAR")
    )
    if item.paths.get("video"):
        feats["visual.video"] = _video_feature(item, raw_dir)
    digests = _file_digests(item, raw_dir)
    feats["visual.exact"] = (
        Feature("visual.exact", GROUP, digests, 1.0, "SHA-1 plików zrzutów i wideo")
        if digests
        else Feature.missing("visual.exact", GROUP, "brak plików zrzutów i wideo")
    )
    return feats


def _file_digests(item: Item, raw_dir: Path) -> list[str]:
    out = set()
    for kind in ("screenshot", "video"):
        for rel in item.paths.get(kind, []):
            h = hashlib.sha1()
            try:
                with (raw_dir / rel).open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                continue
            out.add(h.hexdigest())
    return sorted(out)


def _video_feature(item: Item, raw_dir: Path) -> Feature:
    try:
        import cv2
    except ImportError:
        return Feature.missing(
            "visual.video",
            GROUP,
            "klatki wideo wymagają opcjonalnej zależności opencv (extra 'video')",
        )
    frames = []
    for rel in item.paths.get("video", []):
        cap = cv2.VideoCapture(str(raw_dir / rel))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(1, int(fps * VIDEO_STEP_SECONDS))
        for idx in range(0, max(total, 1), step):
            if len(frames) >= MAX_ASSETS:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                break
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if not _is_informative(img):
                continue
            frames.append(
                {
                    "src": f"{rel}@{idx / fps:.1f}s",
                    "w": img.width,
                    "h": img.height,
                    "phash": str(imagehash.phash(img)),
                }
            )
        cap.release()
    if not frames:
        return Feature.missing("visual.video", GROUP, "nie udało się odczytać klatek wideo")
    return Feature(
        "visual.video", GROUP, frames, 0.7, f"klatki wideo co {VIDEO_STEP_SECONDS}s: pHash"
    )
