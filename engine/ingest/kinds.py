from __future__ import annotations

from pathlib import Path

from engine.schema import Kind

HTML_SUFFIXES = {".html", ".htm"}
MHTML_SUFFIXES = {".mhtml", ".mht"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
ASSET_DIR_SUFFIX = "_files"
ASSET_DIR_NAMES = {"resources"}
IGNORED_DIR_NAMES = {"__macosx"}
KIND_ORDER: tuple[Kind, ...] = (
    "html",
    "har",
    "screenshot",
    "video",
    "meta",
    "url",
    "assets",
)


def kind_of(path: Path) -> Kind | None:
    name = path.name.lower()
    if name == ".ds_store" or name.startswith("._"):
        return None
    if name == ".har" or name.endswith(".har"):
        return "har"
    suffix = path.suffix.lower()
    if suffix in HTML_SUFFIXES or suffix in MHTML_SUFFIXES:
        return "html"
    if suffix in IMAGE_SUFFIXES:
        return "screenshot"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    if suffix == ".json":
        return "meta"
    if suffix == ".url":
        return "url"
    return None


def is_asset_dir(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith(ASSET_DIR_SUFFIX) or lowered in ASSET_DIR_NAMES


def is_skipped_dir(name: str) -> bool:
    return name.startswith(".") or name.lower() in IGNORED_DIR_NAMES


def ordered(paths: dict[Kind, list[str]]) -> dict[Kind, list[str]]:
    return {kind: paths[kind] for kind in KIND_ORDER if paths.get(kind)}


def prefer_plain_html(html: list[str]) -> list[str]:
    plain = [p for p in html if Path(p).suffix.lower() not in MHTML_SUFFIXES]
    return plain or html
