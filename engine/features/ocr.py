from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

from engine.features import media
from engine.schema import Item

VERSION = "1"
MIN_SCORE = 0.6
MIN_ASSET_SIDE = 300
MAX_ASSETS = 6
MAX_IMAGE_BYTES = 20_000_000
ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".pobrane", ".pobierz")
_LOCK = threading.Lock()


@dataclass
class OcrText:
    source: str
    text: str


def available() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _cache_file(path: Path) -> Path:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return media.cache_root() / "ocr" / f"{h.hexdigest()}-{VERSION}.json"


def read_image(path: Path) -> str:
    cache = _cache_file(path)
    if cache.exists():
        try:
            return json.loads(cache.read_text())["text"]
        except (ValueError, KeyError):
            pass
    with _LOCK:
        result, _ = _engine()(str(path))
    lines = [line[1] for line in (result or []) if len(line) > 2 and float(line[2]) >= MIN_SCORE]
    text = " ".join(lines)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"text": text}, ensure_ascii=False))
    return text


def _asset_images(item: Item, raw_dir: Path) -> list[Path]:
    found: list[tuple[int, Path]] = []
    for rel in item.paths.get("assets", []):
        folder = raw_dir / rel
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ASSET_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_IMAGE_BYTES:
                    continue
                with Image.open(path) as img:
                    w, h = img.size
            except (OSError, ValueError, Image.DecompressionBombError):
                continue
            if min(w, h) >= MIN_ASSET_SIDE:
                found.append((w * h, path))
    return [p for _, p in sorted(found, key=lambda x: -x[0])[:MAX_ASSETS]]


def item_texts(item: Item, raw_dir: Path) -> list[OcrText]:
    if not available():
        return []
    raw_dir = Path(raw_dir)
    sources: list[tuple[str, Path]] = []
    for rel in item.paths.get("screenshot", []):
        path = raw_dir / rel
        if path.is_file() and path.stat().st_size <= MAX_IMAGE_BYTES:
            sources.append((f"ocr:{rel}", path))
    for frame in media.item_frames(item, raw_dir):
        sources.append((f"ocr:{frame.src}", Path(frame.path)))
    for path in _asset_images(item, raw_dir):
        sources.append((f"ocr:{path.relative_to(raw_dir)}", path))
    out = []
    seen: set[str] = set()
    for source, path in sources:
        try:
            text = read_image(path).strip()
        except (OSError, ValueError, RuntimeError):
            continue
        if len(text) >= 3 and text not in seen:
            seen.add(text)
            out.append(OcrText(source, text))
    return out
