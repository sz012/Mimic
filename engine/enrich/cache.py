from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

TTL_SECONDS = 30 * 24 * 3600


def default_dir() -> Path:
    return Path(os.environ.get("MIMIC_CACHE_DIR") or "data/cache") / "enrich"


def _safe(key: str) -> str:
    return re.sub(r"[^a-z0-9.\-_]", "_", key.lower())


class Cache:
    def __init__(self, directory: Path | None = None, clock: Callable[[], float] = time.time):
        self.directory = Path(directory) if directory else default_dir()
        self.clock = clock

    def _path(self, kind: str, key: str) -> Path:
        return self.directory / kind / f"{_safe(key)}.json"

    def get(self, kind: str, key: str):
        try:
            data = json.loads(self._path(kind, key).read_text(encoding="utf-8"))
            if self.clock() - float(data["at"]) > TTL_SECONDS:
                return None
            return data["value"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, kind: str, key: str, value) -> None:
        path = self._path(kind, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"at": self.clock(), "value": value}
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            return
