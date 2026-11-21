from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT = 10
USER_AGENT = "mimic-research"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0]).is_global:
                return False
        except ValueError:
            return False
    return bool(infos)


def _open(url: str):
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return opener.open(request, timeout=TIMEOUT)


def fetch_page(url: str, folder: Path) -> Path | None:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if not is_public_host(parsed.hostname):
            return None
        try:
            response = _open(current)
        except urllib.error.HTTPError as err:
            location = (
                err.headers.get("Location") if err.code in (301, 302, 303, 307, 308) else None
            )
            if not location:
                return None
            current = urljoin(current, location)
            continue
        except (urllib.error.URLError, OSError, ValueError):
            return None
        with response:
            if "html" not in (response.headers.get("Content-Type") or "").lower():
                return None
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        target = folder / "fetched.html"
        target.write_bytes(data)
        return target
    return None
