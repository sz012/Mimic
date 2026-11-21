from __future__ import annotations

import io
import os
import uuid
import zipfile
from pathlib import Path, PurePosixPath

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
MAX_UPLOAD_BYTES = 500_000_000
MAX_ZIP_FILES = 2000


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


def _safe_target(folder: Path, name: str) -> Path | None:
    parts = [
        p for p in PurePosixPath(name.replace("\\", "/")).parts if p not in ("", ".", "..", "/")
    ]
    if not parts or parts[0] == "__MACOSX":
        return None
    target = folder.joinpath(*parts).resolve()
    return target if target.is_relative_to(folder.resolve()) else None


def _extract_zip(data: bytes, folder: Path) -> int:
    written = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        if len(members) > MAX_ZIP_FILES:
            raise ValueError(f"archiwum ma za dużo plików ({len(members)} > {MAX_ZIP_FILES})")
        for member in members:
            target = _safe_target(folder, member.filename)
            if target is None:
                continue
            written += member.file_size
            if written > MAX_UPLOAD_BYTES:
                raise ValueError("archiwum po rozpakowaniu przekracza limit rozmiaru")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src:
                target.write_bytes(src.read(MAX_UPLOAD_BYTES))
    return written


def _collect(folder: Path, upload_root: Path) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}
    for current, dirs, files in os.walk(folder):
        dirs[:] = sorted(
            d
            for d in dirs
            if not d.endswith(SKIP_DIR_SUFFIXES)
            and d not in SKIP_DIR_NAMES
            and not d.startswith(".")
        )
        for name in sorted(files):
            full = Path(current) / name
            kind = kind_of(full)
            if kind:
                paths.setdefault(kind, []).append(full.relative_to(upload_root).as_posix())
    return paths


def ingest_upload(files: list[tuple[str, bytes]], url: str | None, upload_root: Path) -> Item:
    token = uuid.uuid4().hex[:10]
    folder = Path(upload_root) / token
    folder.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, data in files:
        total += len(data)
        if total > MAX_UPLOAD_BYTES:
            raise ValueError("przesłane pliki przekraczają limit rozmiaru")
        if name.lower().endswith(".zip"):
            _extract_zip(data, folder)
            continue
        target = _safe_target(folder, PurePosixPath(name.replace("\\", "/")).name)
        if target is not None:
            target.write_bytes(data)
    if url:
        (folder / "input.url").write_text(url.strip() + "\n", encoding="utf-8")
    return Item(id=f"upload/{token}", case_id="upload", paths=_collect(folder, Path(upload_root)))


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
