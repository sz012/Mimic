from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from engine.features.urlnorm import is_common

MAX_HAR_BYTES = 200 * 1024 * 1024
MAX_BODY_BYTES = 2 * 1024 * 1024


@dataclass
class Entry:
    url: str
    host: str
    method: str
    status: int
    redirect_url: str
    ip: str
    resource_type: str
    mime: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _body(content: dict) -> bytes | None:
    text = content.get("text")
    if not text or not isinstance(text, str):
        return None
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(text)[:MAX_BODY_BYTES]
        except ValueError:
            return None
    return text.encode("utf-8", "replace")[:MAX_BODY_BYTES]


def _headers(items) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in items or []:
        if isinstance(h, dict) and isinstance(h.get("name"), str):
            out.setdefault(h["name"].lower(), str(h.get("value", "")))
    return out


def _entry(raw: dict) -> Entry | None:
    request, response = raw.get("request") or {}, raw.get("response") or {}
    url = request.get("url")
    if not isinstance(url, str) or not url:
        return None
    content = response.get("content") or {}
    headers = _headers(response.get("headers"))
    ip = str(raw.get("serverIPAddress") or "").strip("[]")
    try:
        status = int(response.get("status") or 0)
    except (TypeError, ValueError):
        status = 0
    return Entry(
        url=url,
        host=host_of(url),
        method=str(request.get("method") or "GET").upper(),
        status=status,
        redirect_url=str(response.get("redirectURL") or headers.get("location") or ""),
        ip=ip,
        resource_type=str(raw.get("_resourceType") or "").lower(),
        mime=str(content.get("mimeType") or "").split(";")[0].strip().lower(),
        headers=headers,
        body=_body(content),
    )


def load_har(path: Path) -> list[Entry]:
    try:
        if path.stat().st_size > MAX_HAR_BYTES:
            return []
        data = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return []
    raw_entries = (data.get("log") or {}).get("entries") if isinstance(data, dict) else None
    if not isinstance(raw_entries, list):
        return []
    entries = [_entry(e) for e in raw_entries if isinstance(e, dict)]
    return [e for e in entries if e is not None]


def _has_domain(host: str) -> bool:
    return "." in host


def main_entry(entries: list[Entry]) -> Entry | None:
    usable = [e for e in entries if _has_domain(e.host) and not is_common(e.host)]
    documents = [e for e in usable if e.resource_type == "document" and e.status < 400]
    if documents:
        return documents[0]
    html = [e for e in usable if "html" in e.mime and e.status < 400]
    return html[0] if html else (usable[0] if usable else None)


def redirect_hosts(entries: list[Entry], main: Entry | None) -> list[str]:
    if main is None:
        return []
    by_url = {e.url: e for e in entries}
    chain: list[str] = []
    current: Entry | None = entries[0] if entries and entries[0].status in range(300, 400) else main
    seen: set[str] = set()
    while current is not None and current.url not in seen:
        seen.add(current.url)
        if current.host and current.host not in chain:
            chain.append(current.host)
        target = current.redirect_url
        if not target:
            break
        host = host_of(target)
        if host and host not in chain:
            chain.append(host)
        current = by_url.get(target)
    return chain if len(chain) > 1 else []
