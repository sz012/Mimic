from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from engine.enrich.http import HttpJson
from engine.schema import Item

ENDPOINT = "https://graph.facebook.com/v21.0/ads_archive"
GRAPH_HOST = "graph.facebook.com"
FIELDS = (
    "id",
    "page_id",
    "page_name",
    "ad_creative_bodies",
    "ad_creative_link_titles",
    "ad_creative_link_captions",
    "ad_creative_link_descriptions",
    "ad_delivery_start_time",
    "publisher_platforms",
    "languages",
)
DOMAIN = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$")
AD_ID = re.compile(r"^\d{5,25}$")
LIBRARY_URL = "https://www.facebook.com/ads/library/?id="
PAGE_LIMIT = 50


class AdLibraryUnavailable(Exception):
    pass


@dataclass
class AdQuery:
    terms: str
    countries: list[str] = field(default_factory=lambda: ["PL"])
    active_status: str = "ALL"
    max_pages: int = 3


def token() -> str | None:
    return os.environ.get("META_AD_LIBRARY_TOKEN") or None


def _params(query: AdQuery) -> dict[str, str]:
    return {
        "search_terms": query.terms,
        "ad_type": "ALL",
        "ad_reached_countries": json.dumps(query.countries),
        "ad_active_status": query.active_status,
        "fields": ",".join(FIELDS),
        "limit": str(PAGE_LIMIT),
    }


def search(query: AdQuery, transport=None, access_token: str | None = None) -> list[dict]:
    access_token = access_token or token()
    if not access_token:
        raise AdLibraryUnavailable("brak META_AD_LIBRARY_TOKEN")
    transport = transport or HttpJson()
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{ENDPOINT}?{urlencode(_params(query))}"
    ads: list[dict] = []
    for _ in range(max(1, query.max_pages)):
        try:
            page = transport.get(url, headers=headers)
        except (OSError, ValueError) as exc:
            raise AdLibraryUnavailable(f"zapytanie nieudane: {type(exc).__name__}") from exc
        ads.extend(a for a in page.get("data") or [] if isinstance(a, dict))
        url = (page.get("paging") or {}).get("next") or ""
        if not url or urlsplit(url).hostname != GRAPH_HOST:
            break
    return ads


def _first(values) -> str:
    return str(values[0]).strip() if isinstance(values, list) and values else ""


def _landing(captions) -> str | None:
    for caption in captions if isinstance(captions, list) else []:
        domain = str(caption).strip().lower()
        if DOMAIN.match(domain):
            return f"https://{domain}/"
    return None


def ad_document(ad: dict) -> dict:
    ad_id = str(ad["id"])
    body = " ".join(str(b) for b in ad.get("ad_creative_bodies") or [])
    extra = " ".join(str(d) for d in ad.get("ad_creative_link_descriptions") or [])
    document = {
        "extractor": "facebook:ads",
        "id": ad_id,
        "title": _first(ad.get("ad_creative_link_titles")),
        "description": " ".join(p for p in (body, extra) if p),
        "uploader": str(ad.get("page_name") or ""),
        "uploader_id": str(ad.get("page_id") or ""),
        "webpage_url": f"{LIBRARY_URL}{ad_id}",
        "start_time": str(ad.get("ad_delivery_start_time") or ""),
        "platforms": ad.get("publisher_platforms") or [],
    }
    landing = _landing(ad.get("ad_creative_link_captions"))
    if landing:
        document["page_url"] = landing
    return document


def materialize(ads: list[dict], root: Path) -> list[Item]:
    root = Path(root)
    items: list[Item] = []
    for ad in ads:
        ad_id = str(ad.get("id") or "")
        if not AD_ID.match(ad_id):
            continue
        folder = root / ad_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "ad.json").write_text(
            json.dumps(ad_document(ad), ensure_ascii=False), encoding="utf-8"
        )
        items.append(
            Item(id=f"adlib/{ad_id}", case_id="adlib", paths={"meta": [f"{ad_id}/ad.json"]})
        )
    return items
