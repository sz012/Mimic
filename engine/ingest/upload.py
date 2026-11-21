from __future__ import annotations

import io
import os
import stat
import uuid
import zipfile
from pathlib import Path

from engine.ingest import fetch
from engine.ingest.discover import collect_files
from engine.ingest.kinds import is_asset_dir, is_skipped_dir, ordered, prefer_plain_html
from engine.ingest.mhtml import convert_mhtml, safe_name, unique_path
from engine.schema import Item, Kind

MAX_ZIP_FILES = 2000
MAX_UNPACKED_BYTES = 512 * 1024 * 1024


def _unpack_zip(data: bytes, target: Path) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_ZIP_FILES:
            return
        if sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
            return
        remaining = MAX_UNPACKED_BYTES
        for info in infos:
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                continue
            parts = [p for p in info.filename.replace("\\", "/").split("/") if p not in ("", ".")]
            if not parts or any(p == ".." for p in parts) or info.filename.startswith(("/", "\\")):
                continue
            directory = target
            for part in parts[:-1]:
                directory = directory / safe_name(part, "katalog")
            directory.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src:
                content = src.read(min(info.file_size, remaining) + 1)
            if len(content) > remaining:
                return
            remaining -= len(content)
            unique_path(directory, safe_name(parts[-1])).write_bytes(content)


def _store_file(folder: Path, name: str, data: bytes) -> None:
    cleaned = safe_name(name)
    if cleaned.lower().endswith(".zip"):
        target = unique_path(folder, Path(cleaned).stem or "archiwum")
        target.mkdir(parents=True, exist_ok=True)
        _unpack_zip(data, target)
        return
    saved = unique_path(folder, cleaned)
    saved.write_bytes(data)
    if saved.suffix.lower() in (".mhtml", ".mht"):
        convert_mhtml(saved, folder)


def _collect_tree(folder: Path, root: Path) -> dict[Kind, list[str]]:
    paths: dict[Kind, list[str]] = {}
    for current, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not is_skipped_dir(d))
        directory = Path(current)
        asset_dirs = [d for d in dirs if is_asset_dir(d)]
        dirs[:] = [d for d in dirs if not is_asset_dir(d)]
        for kind, rels in collect_files(directory, files, root).items():
            paths.setdefault(kind, []).extend(rels)
        for d in asset_dirs:
            paths.setdefault("assets", []).append((directory / d).relative_to(root).as_posix())
    if "html" in paths:
        paths["html"] = prefer_plain_html(paths["html"])
    return ordered(paths)


def ingest_upload(files: list[tuple[str, bytes]], url: str | None, upload_root: Path) -> Item:
    upload_root = Path(upload_root)
    token = uuid.uuid4().hex[:8]
    folder = upload_root / token
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files:
        _store_file(folder, name, data)
    cleaned_url = (url or "").strip()
    if cleaned_url:
        (folder / "input.url").write_text(cleaned_url + "\n", encoding="utf-8")
        if os.environ.get("MIMIC_ALLOW_FETCH") == "1":
            fetch.fetch_page(cleaned_url, folder)
    return Item(id=f"upload/{token}", case_id="upload", paths=_collect_tree(folder, upload_root))
