from __future__ import annotations

import os
from pathlib import Path

from engine.schema import Item

KIND_BY_SUFFIX = {
    ".html": "html",
    ".htm": "html",
    ".har": "har",
    ".png": "screenshot",
    ".jpg": "screenshot",
    ".jpeg": "screenshot",
    ".webp": "screenshot",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".json": "meta",
    ".url": "url",
}

SKIP_DIR_SUFFIXES = ("_files",)
SKIP_DIR_NAMES = {"resources", "__MACOSX"}


def raw_dir() -> Path:
    return Path(os.environ.get("MIMIC_RAW_DIR", "data/raw"))


def kind_of(path: Path) -> str | None:
    name = path.name.lower()
    if name.startswith(".") and name != ".har":
        return None
    if name.endswith(".har"):
        return "har"
    return KIND_BY_SUFFIX.get(path.suffix.lower())


def discover_items(root: Path) -> list[Item]:
    items: list[Item] = []
    if not root.exists():
        return items
    for case_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for current, dirs, files in os.walk(case_dir):
            dirs[:] = sorted(
                d
                for d in dirs
                if not d.endswith(SKIP_DIR_SUFFIXES)
                and d not in SKIP_DIR_NAMES
                and not d.startswith(".")
            )
            paths: dict[str, list[str]] = {}
            for name in sorted(files):
                full = Path(current) / name
                kind = kind_of(full)
                if kind:
                    paths.setdefault(kind, []).append(str(full.relative_to(root)))
            if paths:
                rel = Path(current).relative_to(root).as_posix()
                items.append(Item(id=rel, case_id=case_dir.name, paths=paths))
    return items


def load_items() -> list[Item]:
    try:
        from engine.store import load_items as store_load_items
    except ImportError:
        store_load_items = None
    if store_load_items is not None:
        loaded = store_load_items()
        if loaded:
            return loaded
    return discover_items(raw_dir())
