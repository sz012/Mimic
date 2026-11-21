from __future__ import annotations

import hashlib
import itertools
import re
from urllib.parse import parse_qsl, urlsplit

TEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fbpixel", re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?(\d{8,20})")),
    ("ga4", re.compile(r"\b(G-[A-Z0-9]{8,12})\b")),
    ("gads", re.compile(r"\b(AW-\d{8,12})\b")),
    ("gtm", re.compile(r"\b(GTM-[A-Z0-9]{4,8})\b")),
    ("ua", re.compile(r"\b(UA-\d{4,10}-\d{1,3})\b")),
    ("tiktok", re.compile(r"ttq\.load\(\s*['\"]([A-Z0-9]{10,24})")),
    ("ym", re.compile(r"\bym\(\s*(\d{6,10})\s*,\s*['\"]init")),
    ("clarity", re.compile(r"clarity\.ms/tag/([a-z0-9]{8,12})")),
    ("hotjar", re.compile(r"\bhjid\s*[:=]\s*(\d{5,9})")),
)
URL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fbpixel", re.compile(r"facebook\.(?:com|net)/tr/?\?[^#]*?\bid=(\d{8,20})")),
    ("gads", re.compile(r"googleadservices\.com/pagead/conversion/(\d{8,12})")),
    ("gads", re.compile(r"google\.[a-z.]+/pagead/1p-conversion/(\d{8,12})")),
    ("ga4", re.compile(r"googletagmanager\.com/gtag/js\?[^#]*?\bid=(G-[A-Z0-9]{8,12})")),
    ("gads", re.compile(r"googletagmanager\.com/gtag/js\?[^#]*?\bid=AW-(\d{8,12})")),
    ("gtm", re.compile(r"googletagmanager\.com/gtm\.js\?[^#]*?\bid=(GTM-[A-Z0-9]{4,8})")),
    ("tiktok", re.compile(r"analytics\.tiktok\.com/[^#]*?\bsdkid=([A-Z0-9]{10,24})")),
    ("ym", re.compile(r"mc\.yandex\.\w+/watch/(\d{6,10})")),
    ("hotjar", re.compile(r"static\.hotjar\.com/c/hotjar-(\d{5,9})")),
)
PIXEL_PARAMS = {"pxl", "fbpx", "pixel_id", "fb_pixel", "fbpixel"}
ID_PARAMS = {
    "utm_id",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "utm_medium",
    "utm_creative",
    "clickid",
    "click_id",
    "subid",
    "sub_id",
    "cid",
    "campaign_id",
    "ad_id",
    "adset_id",
    "ad_name",
    "adset_name",
    "acc",
    "offer",
    "offer_id",
    "aff_id",
    "affid",
    "pid",
    "key",
    "token",
    "access_token",
    "pxl",
    "fbpx",
    "pixel_id",
}
SECRET_PARAMS = {"key", "token", "access_token"}
MIN_ID_LENGTH = 6
MIN_CASE_TRANSITIONS = 4


def _case_transitions(value: str) -> int:
    letters = [c for c in value if c.isalpha()]
    return sum(1 for a, b in itertools.pairwise(letters) if a.isupper() != b.isupper())


def is_identifier(value: str) -> bool:
    if len(value) < MIN_ID_LENGTH or " " in value or "{" in value or "[REDACTED]" in value:
        return False
    if any(c.isdigit() for c in value):
        return True
    return value.isalpha() and len(value) >= 10 and _case_transitions(value) >= MIN_CASE_TRANSITIONS


def _secret(value: str) -> str:
    return "sha1:" + hashlib.sha1(value.encode()).hexdigest()[:12]


def trackers_in_text(text: str) -> set[str]:
    found = set()
    for kind, pattern in TEXT_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1)
            if kind in ("ga4", "ua", "gtm", "gads") and not any(c.isdigit() for c in value):
                continue
            found.add(f"{kind}:{value}")
    return found


def trackers_in_url(url: str) -> set[str]:
    found = set()
    for kind, pattern in URL_PATTERNS:
        for match in pattern.finditer(url):
            value = match.group(1)
            found.add(
                f"{kind}:AW-{value}"
                if kind == "gads" and not value.startswith("AW-")
                else f"{kind}:{value}"
            )
    return found


def url_params(url: str) -> tuple[set[str], set[str]]:
    params: set[str] = set()
    trackers: set[str] = set()
    try:
        query = urlsplit(url).query
    except ValueError:
        return params, trackers
    for name, value in parse_qsl(query, keep_blank_values=False):
        lowered = name.lower()
        if lowered in PIXEL_PARAMS and value.isdigit() and len(value) >= 8:
            trackers.add(f"fbpixel:{value}")
        if lowered in ID_PARAMS and is_identifier(value):
            shown = _secret(value) if lowered in SECRET_PARAMS else value
            params.add(f"{lowered}={shown}")
    return params, trackers
