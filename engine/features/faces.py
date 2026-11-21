from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
from PIL import Image

from engine.features.visual import _asset_dirs, _is_informative, _open
from engine.schema import Feature, Item

GROUP = "person"
NAME = "person.faces"
VECTORS = "person.face_vectors"
MODEL = "buffalo_l"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
MIN_DETECTION = 0.6
MIN_FACE_SIDE = 40
MAX_IMAGES = 40
MAX_FACES = 12
SAME_FACE = 0.85
MAX_IMAGE_BYTES = 15_000_000
MAX_HAR_BYTES = 120_000_000
DEFAULT_THRESHOLD = 0.5
DEFAULT_REFS = Path(__file__).resolve().parents[2] / "data" / "refs" / "images"
INSTALL_HINT = "dopasowanie twarzy wymaga opcjonalnej zależności insightface (extra 'faces')"
LOAD_ERRORS = (OSError, RuntimeError, ValueError, AssertionError, ImportError)

Embedder = Callable[[Image.Image], list[tuple[np.ndarray, float]]]
Gallery = dict[str, list[np.ndarray]]

_lock = threading.Lock()
_embedder: tuple[Embedder | None, str] | None = None
_galleries: dict[str, Gallery] = {}


def refs_dir() -> Path:
    return Path(os.environ.get("MIMIC_FACE_REFS") or DEFAULT_REFS)


def threshold() -> float:
    try:
        return float(os.environ.get("MIMIC_FACE_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD


def reference_images() -> dict[str, list[Path]]:
    root = refs_dir()
    try:
        folders = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return {}
    out = {}
    for folder in folders:
        files = sorted(
            p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        )
        if files:
            out[folder.name] = files
    return out


def gallery_signature() -> str:
    h = hashlib.sha1()
    for name, files in reference_images().items():
        for path in files:
            try:
                st = path.stat()
            except OSError:
                continue
            h.update(f"{name}/{path.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:12]


def installed() -> bool:
    return importlib.util.find_spec("insightface") is not None


def state() -> str:
    return f"{'on' if installed() else 'off'}-{gallery_signature()}-{threshold()}"


def _insightface_embedder() -> tuple[Embedder | None, str]:
    if not installed():
        return None, INSTALL_HINT
    try:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(
            name=MODEL,
            root=os.environ.get("MIMIC_MODELS_DIR", "models"),
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
    except LOAD_ERRORS as exc:
        return None, f"nie udało się załadować modelu twarzy {MODEL}: {exc!r}"

    def run(img: Image.Image) -> list[tuple[np.ndarray, float]]:
        arr = np.asarray(img.convert("RGB"))[:, :, ::-1]
        out = []
        for face in app.get(arr):
            x1, y1, x2, y2 = face.bbox
            if face.det_score < MIN_DETECTION or min(x2 - x1, y2 - y1) < MIN_FACE_SIDE:
                continue
            out.append((np.asarray(face.normed_embedding, dtype=np.float32), float(face.det_score)))
        return out

    return run, ""


def get_embedder() -> tuple[Embedder | None, str]:
    global _embedder
    with _lock:
        if _embedder is None:
            _embedder = _insightface_embedder()
        return _embedder


def _gallery_cache_file(signature: str) -> Path:
    cache = Path(os.environ.get("MIMIC_CACHE_DIR", "data/cache"))
    return cache / "faces" / f"gallery-{signature}.json"


def _load_cached(signature: str) -> Gallery | None:
    try:
        data = json.loads(_gallery_cache_file(signature).read_text())
    except (OSError, ValueError):
        return None
    try:
        return {
            n: [np.asarray(v, dtype=np.float32) for v in vs] for n, vs in data["persons"].items()
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _save_cached(signature: str, gallery: Gallery) -> None:
    path = _gallery_cache_file(signature)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"persons": {n: [v.tolist() for v in vs] for n, vs in gallery.items()}}
        path.write_text(json.dumps(payload))
    except OSError:
        return


def build_gallery(embedder: Embedder) -> Gallery:
    gallery: Gallery = {}
    for name, files in reference_images().items():
        for path in files:
            try:
                img = _open(path.read_bytes())
            except OSError:
                continue
            if img is None:
                continue
            faces = embedder(img)
            if faces:
                best = max(faces, key=lambda f: f[1])
                gallery.setdefault(name, []).append(best[0])
    return gallery


def get_gallery(embedder: Embedder) -> Gallery:
    signature = gallery_signature()
    with _lock:
        if signature in _galleries:
            return _galleries[signature]
        gallery = _load_cached(signature) or build_gallery(embedder)
        _save_cached(signature, gallery)
        _galleries[signature] = gallery
        return gallery


def best_match(emb: np.ndarray, gallery: Gallery, limit: float) -> tuple[str | None, float]:
    best_name, best = None, 0.0
    for name, refs in gallery.items():
        score = max(float(np.dot(emb, ref)) for ref in refs)
        if score > best:
            best_name, best = name, score
    return (best_name, best) if best >= limit else (None, best)


def _har_images(item: Item, raw_dir: Path) -> Iterator[bytes]:
    for rel in item.paths.get("har", []):
        try:
            if (raw_dir / rel).stat().st_size > MAX_HAR_BYTES:
                continue
            har = json.loads((raw_dir / rel).read_bytes())
        except (OSError, ValueError):
            continue
        for entry in har.get("log", {}).get("entries", []):
            content = entry.get("response", {}).get("content", {})
            mime = content.get("mimeType") or ""
            text = content.get("text")
            if not mime.startswith("image/") or "svg" in mime or not text:
                continue
            try:
                yield (
                    base64.b64decode(text)
                    if content.get("encoding") == "base64"
                    else text.encode("latin-1")
                )
            except (ValueError, UnicodeEncodeError):
                continue


def _file_images(item: Item, raw_dir: Path) -> Iterator[bytes]:
    paths = [raw_dir / rel for rel in item.paths.get("screenshot", [])]
    for folder in _asset_dirs(item, raw_dir):
        paths.extend(
            p
            for p in sorted(folder.rglob("*"))
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        )
    for path in paths:
        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                continue
            yield path.read_bytes()
        except OSError:
            continue


def item_images(item: Item, raw_dir: Path) -> list[Image.Image]:
    out, seen = [], set()
    for data in [*_file_images(item, raw_dir), *_har_images(item, raw_dir)]:
        if len(out) >= MAX_IMAGES:
            break
        digest = hashlib.sha1(data).digest()
        if digest in seen:
            continue
        seen.add(digest)
        img = _open(data)
        if img is not None and _is_informative(img):
            out.append(img)
    return out


def _distinct(vectors: list[np.ndarray]) -> list[np.ndarray]:
    kept: list[np.ndarray] = []
    for vec in vectors:
        if all(float(np.dot(vec, other)) < SAME_FACE for other in kept):
            kept.append(vec)
    return kept[:MAX_FACES]


def extract(item: Item, raw_dir: Path) -> dict[str, Feature]:
    embedder, reason = get_embedder()
    if embedder is None:
        return {
            NAME: Feature.missing(NAME, GROUP, reason),
            VECTORS: Feature.missing(VECTORS, GROUP, reason),
        }
    images = item_images(item, Path(raw_dir))
    if not images:
        none = "brak obrazów do analizy twarzy"
        return {
            NAME: Feature.missing(NAME, GROUP, none),
            VECTORS: Feature.missing(VECTORS, GROUP, none),
        }
    found = [emb for img in images for emb, _ in embedder(img)]
    summary = f"{len(found)} twarzy na {len(images)} obrazach"
    feats: dict[str, Feature] = {}
    distinct = _distinct(found)
    feats[VECTORS] = (
        Feature(
            VECTORS,
            GROUP,
            [[round(float(x), 4) for x in vec] for vec in distinct],
            0.8,
            f"{summary}, {len(distinct)} różnych",
        )
        if distinct
        else Feature.missing(VECTORS, GROUP, f"{summary}: nie wykryto twarzy")
    )
    gallery = get_gallery(embedder)
    if not gallery:
        feats[NAME] = Feature.missing(
            NAME, GROUP, "brak obrazów referencyjnych (data/refs/images/<imię nazwisko>/)"
        )
        return feats
    limit = threshold()
    hits: dict[str, float] = {}
    for emb in found:
        name, score = best_match(emb, gallery, limit)
        if name:
            hits[name] = max(hits.get(name, 0.0), score)
    feats[NAME] = (
        Feature(
            NAME,
            GROUP,
            sorted(hits),
            round(min(1.0, max(hits.values())), 3),
            f"{summary}, dopasowanie do bazy referencyjnej (próg {limit})",
        )
        if hits
        else Feature.missing(
            NAME, GROUP, f"{summary}, brak dopasowania do bazy referencyjnej (próg {limit})"
        )
    )
    return feats
