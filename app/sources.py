from __future__ import annotations

import os
from pathlib import Path

from engine.ingest import discover_items, ingest_upload
from engine.schema import Item
from engine.store import Store, default_path

__all__ = ["discover_items", "ingest_upload", "load_items", "open_store", "raw_dir"]


def raw_dir() -> Path:
    return Path(os.environ.get("MIMIC_RAW_DIR", "data/raw"))


def open_store() -> Store:
    return Store(default_path())


def load_items() -> list[Item]:
    return discover_items(raw_dir())
