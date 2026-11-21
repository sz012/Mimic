from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from urllib.parse import urlsplit

import tldextract

COMMON_DOMAINS = frozenset(
    {
        "google.com",
        "googleapis.com",
        "gstatic.com",
        "googleusercontent.com",
        "googletagmanager.com",
        "google-analytics.com",
        "googleadservices.com",
        "googlesyndication.com",
        "doubleclick.net",
        "youtube.com",
        "ytimg.com",
        "youtu.be",
        "facebook.com",
        "facebook.net",
        "fbcdn.net",
        "instagram.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "w3.org",
        "schema.org",
        "jquery.com",
        "jsdelivr.net",
        "cloudflare.com",
        "cloudflareinsights.com",
        "unpkg.com",
        "bootstrapcdn.com",
        "fontawesome.com",
        "wikipedia.org",
        "apple.com",
        "microsoft.com",
        "gravatar.com",
        "wp.com",
        "wordpress.org",
        "github.com",
        "hcaptcha.com",
        "recaptcha.net",
        "polyfill.io",
    }
)
SHARED_IP_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)
UNINFORMATIVE_IPS = frozenset({"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9"})
STATIC_SUFFIXES = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".map",
    ".mp4",
    ".ts",
    ".m3u8",
)
_ID_SEGMENT = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,}|\d{4,}|[A-Za-z0-9_-]{24,})$",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _extractor() -> tldextract.TLDExtract:
    return tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def is_shared_ip(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if not address.is_global or host in UNINFORMATIVE_IPS:
        return True
    return any(
        address in network for network in SHARED_IP_NETWORKS if network.version == address.version
    )


def registrable_domain(host: str) -> str | None:
    host = host.strip(".").lower()
    if not host or "." not in host or is_ip(host):
        return None
    parts = _extractor()(host)
    if parts.domain and parts.suffix:
        return f"{parts.domain}.{parts.suffix}"
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else None


def is_common(host: str) -> bool:
    domain = registrable_domain(host)
    return domain in COMMON_DOMAINS if domain else False


def normalize_path(url: str) -> str | None:
    try:
        path = urlsplit(url).path
    except ValueError:
        return None
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    normalized = ["{id}" if _ID_SEGMENT.match(s) else s.lower() for s in segments]
    result = "/" + "/".join(normalized)
    if result.endswith(STATIC_SUFFIXES):
        return None
    if len(normalized) < 2 and "." not in normalized[-1]:
        return None
    return result
