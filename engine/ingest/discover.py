from __future__ import annotations

import os
from pathlib import Path

from engine.ingest.kinds import is_asset_dir, is_skipped_dir, kind_of, ordered, prefer_plain_html
from engine.schema import Item, Kind


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def collect_files(directory: Path, names: list[str], root: Path) -> dict[Kind, list[str]]:
    paths: dict[Kind, list[str]] = {}
    for name in sorted(names):
        full = directory / name
        if not full.is_file():
            continue
        kind = kind_of(full)
        if kind:
            paths.setdefault(kind, []).append(_relative(full, root))
    if "html" in paths:
        paths["html"] = prefer_plain_html(paths["html"])
    return paths


def discover_items(root: Path) -> list[Item]:
    root = Path(root)
    if not root.is_dir():
        return []
    items: list[Item] = []
    case_dirs = sorted(p for p in root.iterdir() if p.is_dir() and not is_skipped_dir(p.name))
    for case_dir in case_dirs:
        for current, dirs, files in os.walk(case_dir):
            dirs[:] = sorted(d for d in dirs if not is_skipped_dir(d))
            asset_dirs = [d for d in dirs if is_asset_dir(d)]
            dirs[:] = [d for d in dirs if not is_asset_dir(d)]
            directory = Path(current)
            paths = collect_files(directory, files, root)
            if not paths:
                continue
            if asset_dirs:
                paths["assets"] = [_relative(directory / d, root) for d in asset_dirs]
            items.append(
                Item(id=_relative(directory, root), case_id=case_dir.name, paths=ordered(paths))
            )
    return items
