from __future__ import annotations

import email
import email.policy
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

MAX_PARTS = 2000
MAX_NAME = 120


def safe_name(name: str, fallback: str = "plik") -> str:
    base = Path(name.replace("\\", "/")).name
    if base.lower() == ".har":
        return ".har"
    cleaned = re.sub(r"[^\w.\- ()]", "_", base).strip(" .")
    return cleaned[:MAX_NAME] or fallback


def unique_path(directory: Path, name: str) -> Path:
    target = directory / name
    counter = 2
    stem, suffix = Path(name).stem, Path(name).suffix
    while target.exists():
        target = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return target


def convert_mhtml(source: Path, target_dir: Path) -> Path | None:
    with source.open("rb") as fh:
        message = email.message_from_binary_file(fh, policy=email.policy.default)
    html_part = None
    resources = []
    for part in message.walk():
        if part.is_multipart():
            continue
        if html_part is None and part.get_content_type() == "text/html":
            html_part = part
        else:
            resources.append(part)
    if html_part is None:
        return None
    stem = safe_name(source.stem, "strona")
    html_path = unique_path(target_dir, f"{stem}.html")
    html_path.write_bytes(html_part.get_payload(decode=True) or b"")
    assets = target_dir / f"{html_path.stem}_files"
    for index, part in enumerate(resources[:MAX_PARTS]):
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        location = urlparse(part.get("Content-Location", "") or "").path
        extension = mimetypes.guess_extension(part.get_content_type()) or ""
        name = safe_name(Path(location).name, f"zasob_{index}{extension}")
        assets.mkdir(exist_ok=True)
        unique_path(assets, name).write_bytes(payload)
    return html_path


def html_text_from_mhtml(source: Path) -> str | None:
    try:
        with source.open("rb") as fh:
            message = email.message_from_binary_file(fh, policy=email.policy.default)
    except OSError:
        return None
    for part in message.walk():
        if not part.is_multipart() and part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True) or b""
            return payload.decode(part.get_content_charset() or "utf-8", "replace")
    return None
