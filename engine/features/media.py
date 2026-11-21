from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import imagehash
from PIL import Image

from engine.schema import Item

VERSION = "2"
STEP_SECONDS = 1.0
MAX_GAP_SECONDS = 10.0
MAX_FRAMES = 30
SCENE_CHANGE = 10
MAX_SIDE = 960


@dataclass
class Frame:
    src: str
    path: str
    second: float
    phash: str


def cache_root() -> Path:
    return Path(os.environ.get("MIMIC_CACHE_DIR", "data/cache"))


def opencv_available() -> bool:
    return importlib.util.find_spec("cv2") is not None


def _frames_dir(video: Path) -> Path:
    st = video.stat()
    key = hashlib.sha1(
        f"{video.resolve()}:{st.st_size}:{int(st.st_mtime)}:{VERSION}".encode()
    ).hexdigest()[:16]
    return cache_root() / "frames" / key


def _read_index(folder: Path) -> list[Frame] | None:
    index = folder / "index.json"
    if not index.exists():
        return None
    try:
        return [Frame(**f) for f in json.loads(index.read_text())]
    except (ValueError, TypeError):
        return None


def _downscale(img: Image.Image) -> Image.Image:
    if max(img.size) <= MAX_SIDE:
        return img
    ratio = MAX_SIDE / max(img.size)
    return img.resize((int(img.width * ratio), int(img.height * ratio)))


def key_frames(video: Path, rel: str) -> list[Frame]:
    import cv2

    folder = _frames_dir(video)
    cached = _read_index(folder)
    if cached is not None:
        return cached
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(fps * STEP_SECONDS))
    folder.mkdir(parents=True, exist_ok=True)
    frames: list[Frame] = []
    last = None
    last_second = -MAX_GAP_SECONDS
    for idx in range(0, max(total, 1), step):
        if len(frames) >= MAX_FRAMES:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, raw = cap.read()
        if not ok:
            break
        img = _downscale(Image.fromarray(cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)))
        h = imagehash.phash(img)
        second = round(idx / fps, 1)
        if last is not None and h - last < SCENE_CHANGE and second - last_second < MAX_GAP_SECONDS:
            continue
        last, last_second = h, second
        out = folder / f"{len(frames):03d}.jpg"
        img.save(out, quality=85)
        frames.append(Frame(src=f"{rel}@{second}s", path=str(out), second=second, phash=str(h)))
    cap.release()
    (folder / "index.json").write_text(json.dumps([asdict(f) for f in frames]))
    return frames


def item_frames(item: Item, raw_dir: Path) -> list[Frame]:
    if not item.paths.get("video") or not opencv_available():
        return []
    frames: list[Frame] = []
    for rel in item.paths["video"]:
        path = Path(raw_dir) / rel
        if path.is_file():
            frames.extend(key_frames(path, rel))
    return frames
