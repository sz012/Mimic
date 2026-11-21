from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from engine import enrich
from engine.features.harparse import Entry, host_of, load_har, main_entry, redirect_hosts
from engine.features.trackers import trackers_in_text, trackers_in_url, url_params
from engine.features.urlnorm import (
    is_common,
    is_ip,
    is_shared_ip,
    normalize_path,
    registrable_domain,
)
from engine.schema import Feature, Item

GROUP = "infra"
ENRICH_NAMES = ("infra.created", "infra.registrar", "infra.nameservers", "infra.cert_sans")
VERSION = "2"
CONF_HAR = 0.9
CONF_META = 0.8
CONF_HTML = 0.7
CONF_URL = 0.5
CONF_ENRICH = 0.8
MAX_ENRICH_DOMAINS = 3
ENRICH_OFF = "wzbogacenie wyłączone (MIMIC_ENRICH=0)"
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_URLS_PER_HTML = 400
MAX_NAME_LENGTH = 200
NAMES = (
    "infra.domain",
    "infra.hosts",
    "infra.third_party_hosts",
    "infra.tracker_ids",
    "infra.url_params",
    "infra.redirect_chain",
    "infra.endpoints",
    "infra.favicon",
    "infra.ip",
    "infra.server",
    "infra.ad_account",
    "infra.created",
    "infra.registrar",
    "infra.nameservers",
    "infra.cert_sans",
)
SAVED_FROM = re.compile(r"saved from url=\(\d+\)(\S+)")
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>\\)]+")
ICON_MIMES = {"image/x-icon", "image/vnd.microsoft.icon", "image/ico"}
XHR_TYPES = {"xhr", "fetch", "ping"}


@dataclass
class Acc:
    values: dict[str, dict[str, None]] = field(default_factory=dict)
    conf: dict[str, float] = field(default_factory=dict)
    sources: dict[str, list[str]] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    def add(self, name: str, items, confidence: float, source: str) -> None:
        added = False
        bucket = self.values.setdefault(name, {})
        for value in items:
            if value:
                bucket[value] = None
                added = True
        if added:
            self.conf[name] = max(self.conf.get(name, 0.0), confidence)
            if source not in self.sources.setdefault(name, []):
                self.sources[name].append(source)

    def get(self, name: str) -> list[str]:
        return list(self.values.get(name, {}))


def _read_text(path: Path) -> str:
    try:
        with path.open("rb") as fh:
            return fh.read(MAX_HTML_BYTES).decode("utf-8", "replace")
    except OSError:
        return ""


def _page_url(acc: Acc, url: str, confidence: float, source: str) -> None:
    parts = _split(url)
    if parts is None or not parts.hostname:
        return
    domain = registrable_domain(parts.hostname)
    if domain:
        acc.add("infra.domain", [domain], confidence, source)
    host = parts.hostname.lower()
    if "." in host:
        acc.add("infra.hosts", [host], confidence, source)
    params, trackers = url_params(url)
    acc.add("infra.url_params", params, confidence, source)
    acc.add("infra.tracker_ids", trackers | trackers_in_url(url), confidence, source)


def _split(url: str):
    try:
        return urlsplit(url.strip())
    except ValueError:
        return None


def _from_har(acc: Acc, path: Path, rel: str) -> None:
    entries = load_har(path)
    source = f"har:{rel}"
    if not entries:
        return
    main = main_entry(entries)
    if main is not None:
        _page_url(acc, main.url, CONF_HAR, source)
        _first_party_details(acc, entries, main, source)
    hosts = {e.host for e in entries if e.host and ("." in e.host or is_ip(e.host))}
    acc.add("infra.hosts", sorted(hosts), CONF_HAR, source)
    trackers: set[str] = set()
    for entry in entries:
        trackers |= trackers_in_url(entry.url)
        if entry.body is not None and "html" in entry.mime:
            trackers |= trackers_in_text(entry.body.decode("utf-8", "replace"))
    acc.add("infra.tracker_ids", trackers, CONF_HAR, source)
    chain = redirect_hosts(entries, main)
    acc.add("infra.redirect_chain", chain, CONF_HAR, source)
    icons = [e for e in entries if e.mime in ICON_MIMES and e.body]
    acc.add("infra.favicon", [hashlib.sha1(e.body).hexdigest() for e in icons], CONF_HAR, source)


def _first_party_details(acc: Acc, entries: list[Entry], main: Entry, source: str) -> None:
    domain = registrable_domain(main.host)
    own = [e for e in entries if registrable_domain(e.host) == domain]
    acc.add(
        "infra.ip",
        sorted({e.ip for e in own if e.ip and not is_shared_ip(e.ip)}),
        CONF_HAR,
        source,
    )
    endpoints = {
        normalize_path(e.url)
        for e in own
        if e.method == "POST" or e.resource_type in XHR_TYPES or e is main
    }
    acc.add("infra.endpoints", sorted(p for p in endpoints if p), CONF_HAR, source)
    server = []
    for header in ("server", "x-powered-by"):
        value = main.headers.get(header)
        if value:
            server.append(f"{header}:{value.strip().lower()[:40]}")
    acc.add("infra.server", server, CONF_HAR, source)


def _favicon_from_assets(soup: BeautifulSoup, item: Item, raw_dir: Path) -> list[str]:
    names: set[str] = set()
    hashes: list[str] = []
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" not in rel:
            continue
        href = str(link["href"]).strip()
        if href.startswith("data:"):
            hashes.append(hashlib.sha1(href.encode("utf-8", "replace")).hexdigest())
            continue
        name = Path(urlsplit(href).path).name
        if name and len(name) < MAX_NAME_LENGTH:
            names.add(name)
    for directory in item.paths.get("assets", []):
        for name in names:
            try:
                candidate = raw_dir / directory / name
                if candidate.is_file():
                    hashes.append(hashlib.sha1(candidate.read_bytes()).hexdigest())
            except OSError:
                continue
    return hashes


def _from_html(acc: Acc, path: Path, rel: str, item: Item, raw_dir: Path) -> None:
    text = _read_text(path)
    if not text:
        return
    source = f"html:{rel}"
    for match in SAVED_FROM.finditer(text):
        if match.group(1).startswith("http"):
            _page_url(acc, match.group(1), CONF_HTML, source)
            break
    urls = URL_IN_TEXT.findall(text)[:MAX_URLS_PER_HTML]
    hosts = {host_of(u) for u in urls}
    acc.add("infra.hosts", sorted(h for h in hosts if "." in h), CONF_HTML, source)
    trackers = trackers_in_text(text)
    for url in urls:
        trackers |= trackers_in_url(url)
    acc.add("infra.tracker_ids", trackers, CONF_HTML, source)
    soup = BeautifulSoup(text, "lxml")
    endpoints = set()
    for form in soup.find_all("form", action=True):
        action = str(form["action"])
        endpoints.add(normalize_path(action))
        if action.startswith("http"):
            _page_url_hosts_only(acc, action, source)
    acc.add("infra.endpoints", sorted(p for p in endpoints if p), CONF_HTML, source)
    acc.add("infra.favicon", _favicon_from_assets(soup, item, raw_dir), CONF_HTML, source)
    refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.IGNORECASE)})
    if refresh and refresh.get("content"):
        match = re.search(r"url\s*=\s*['\"]?([^'\";]+)", str(refresh["content"]), re.IGNORECASE)
        target = host_of(match.group(1)) if match else ""
        base = acc.get("infra.domain")
        if target and base:
            acc.add("infra.redirect_chain", [base[0], target], CONF_HTML, source)
    canonical = soup.find("link", rel="canonical", href=True) or soup.find(
        "meta", property="og:url", content=True
    )
    if canonical is not None:
        value = canonical.get("href") or canonical.get("content")
        if value and value.startswith("http"):
            domain = registrable_domain(host_of(value))
            if domain:
                acc.add("infra.domain", [domain], CONF_HTML, source)


def _page_url_hosts_only(acc: Acc, url: str, source: str) -> None:
    host = host_of(url)
    if "." in host:
        acc.add("infra.hosts", [host], CONF_HTML, source)


def _from_meta(acc: Acc, path: Path, rel: str) -> None:
    try:
        data = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    source = f"meta:{rel}"
    page_url = data.get("page_url")
    if isinstance(page_url, str) and page_url.startswith("http"):
        _page_url(acc, page_url, CONF_META, source)
    uploader = data.get("playlist_uploader") or data.get("uploader")
    extractor = str(data.get("extractor") or "").split(":")[0].lower()
    if isinstance(uploader, str) and uploader.strip() and extractor:
        acc.add("infra.ad_account", [f"{extractor}:{uploader.strip().lower()}"], CONF_META, source)


def _from_url_file(acc: Acc, path: Path, rel: str) -> None:
    text = _read_text(path).strip().splitlines()
    if text and text[0].startswith("http"):
        _page_url(acc, text[0], CONF_URL, f"url:{rel}")


def _third_party(acc: Acc) -> list[str]:
    own = set(acc.get("infra.domain"))
    hosts = acc.get("infra.hosts")
    if not own:
        return []
    return sorted(
        h for h in hosts if not is_ip(h) and registrable_domain(h) not in own and not is_common(h)
    )


def _public_hosts(acc: Acc) -> list[str]:
    return sorted(h for h in acc.get("infra.hosts") if is_ip(h) or not is_common(h))


def _apply_enrichment(acc: Acc) -> None:
    domains = acc.get("infra.domain")[:MAX_ENRICH_DOMAINS]
    if not enrich.enabled():
        for name in ENRICH_NAMES:
            acc.notes[name] = ENRICH_OFF
        return
    if not domains:
        for name in ENRICH_NAMES:
            acc.notes[name] = "nieznana domena strony głównej"
        return
    created: list[str] = []
    for domain in domains:
        info = enrich.lookup_domain(domain)
        source = f"rdap/dns/crt.sh:{domain}"
        if info.created:
            created.append(info.created)
        acc.add("infra.registrar", [info.registrar] if info.registrar else [], CONF_ENRICH, source)
        acc.add("infra.nameservers", info.nameservers, CONF_ENRICH, source)
        acc.add("infra.cert_sans", info.cert_sans, CONF_ENRICH, source)
        acc.add("infra.ip", info.a_records, CONF_ENRICH, source)
        for name, error in (
            ("rdap", "infra.created"),
            ("dns", "infra.nameservers"),
            ("crtsh", "infra.cert_sans"),
        ):
            if name in info.errors:
                acc.notes.setdefault(error, f"{name}: {info.errors[name]}")
    if created:
        acc.add("infra.created", [min(created)], CONF_ENRICH, "rdap")


def _missing_reason(item: Item, name: str, derived_from_domain: bool = False) -> str:
    if derived_from_domain:
        return "nieznana domena strony głównej"
    if not item.paths.get("har") and name in ("infra.ip", "infra.server", "infra.redirect_chain"):
        return "brak pliku HAR"
    return "nie znaleziono w dostępnych plikach"


def _final_value(name: str, values: list[str]):
    if name == "infra.redirect_chain":
        return values
    if name == "infra.created":
        return values[0]
    return sorted(values)


def extract(item: Item, raw_dir: Path) -> dict[str, Feature]:
    raw_dir = Path(raw_dir)
    acc = Acc()
    for rel in item.paths.get("har", []):
        _from_har(acc, raw_dir / rel, rel)
    for rel in item.paths.get("meta", []):
        _from_meta(acc, raw_dir / rel, rel)
    for rel in item.paths.get("url", []):
        _from_url_file(acc, raw_dir / rel, rel)
    for rel in item.paths.get("html", []):
        _from_html(acc, raw_dir / rel, rel, item, raw_dir)
    _apply_enrichment(acc)
    hosts_all = acc.get("infra.hosts")
    acc.values["infra.hosts"] = {h: None for h in _public_hosts(acc)}
    third = _third_party(acc)
    if third:
        acc.add("infra.third_party_hosts", third, acc.conf.get("infra.hosts", CONF_HTML), "hosty")
        acc.sources["infra.third_party_hosts"] = acc.sources.get("infra.hosts", [])
    features: dict[str, Feature] = {}
    for name in NAMES:
        values = acc.get(name)
        if values:
            confidence = round(acc.conf.get(name, CONF_HTML), 3)
            source = "; ".join(acc.sources.get(name, [])[:4])
            value = _final_value(name, values)
            features[name] = Feature(name, GROUP, value, confidence, source)
        else:
            derived = name == "infra.third_party_hosts" and not acc.get("infra.domain")
            reason = acc.notes.get(name) or _missing_reason(item, name, derived and bool(hosts_all))
            features[name] = Feature.missing(name, GROUP, reason)
    return features
