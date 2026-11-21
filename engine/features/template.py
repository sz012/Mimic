from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, Tag

from engine.features.harparse import load_har, main_entry
from engine.ingest.mhtml import html_text_from_mhtml
from engine.schema import Feature, Item

GROUP = "template"
VERSION = "1"
CONF = 0.7
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_ASSET_FILES = 400
MAX_ITEMS_PER_FEATURE = 300
SHINGLE = 3
MAX_DEPTH = 8
NAMES = (
    "template.dom_simhash",
    "template.inline_scripts",
    "template.scripts",
    "template.css_classes",
    "template.asset_names",
    "template.form_fields",
    "template.html_comments",
    "template.meta",
)
SKIP_STRUCTURE = {"script", "style", "noscript", "svg", "head", "meta", "link", "title"}
TRACKER_MARKERS = (
    "fbq(",
    "gtag(",
    "datalayer",
    "googletagmanager",
    "ttq.",
    "clarity",
    "hotjar",
    "_hjsettings",
    "google-analytics",
)
GENERIC_COMMENT_MARKERS = (
    "google tag",
    "facebook pixel",
    "meta pixel",
    "analytics",
    "saved from url",
    "end of",
    "[if ",
)
GENERIC_CLASS = re.compile(
    r"^(?:col|row|container|offset|btn|nav|navbar|card|modal|fade|show|active|hidden|d|m[trblxy]?"
    r"|p[trblxy]?|text|bg|border|w|h|flex|grid|justify|align|fw|fs|rounded|shadow|float|clearfix"
    r"|wp|elementor|fa|fas|far|fab|icon|img|image|logo|header|footer|main|content|wrapper|section"
    r"|title|button|link|item|list|form|input|label|menu|open|close|top|bottom|left|right|center)"
    r"(?:[-_].*)?$",
    re.IGNORECASE,
)
GENERIC_SCRIPT = re.compile(
    r"^(?:jquery|bootstrap|popper|gtag|analytics|polyfill|modernizr|lodash|react|vue)",
    re.IGNORECASE,
)
GENERIC_FIELDS = frozenset(
    {
        "name",
        "phone",
        "tel",
        "email",
        "address",
        "city",
        "zip",
        "first_name",
        "last_name",
        "surname",
        "country",
        "message",
        "comment",
        "q",
        "s",
        "search",
    }
)
META_KEYS = ("generator", "og:site_name", "author", "application-name", "theme-color", "fb:app_id")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".avif"}
HASHY_NAME = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{12,}|\d+)$",
    re.IGNORECASE,
)
VERSION_SUFFIX = re.compile(r"[.\-_][0-9a-f]{6,}(?=\.[a-z0-9]+$)", re.IGNORECASE)


@dataclass
class Page:
    source: str
    soup: BeautifulSoup


@dataclass
class Collected:
    pages: list[Page] = field(default_factory=list)
    assets: list[Path] = field(default_factory=list)


def _soup(text: str, source: str) -> Page | None:
    if not text.strip():
        return None
    return Page(source, BeautifulSoup(text, "lxml"))


def _load_pages(item: Item, raw_dir: Path) -> list[Page]:
    pages: list[Page] = []
    for rel in item.paths.get("html", []):
        path = raw_dir / rel
        if path.suffix.lower() in (".mhtml", ".mht"):
            text = html_text_from_mhtml(path)
        else:
            try:
                with path.open("rb") as fh:
                    text = fh.read(MAX_HTML_BYTES).decode("utf-8", "replace")
            except OSError:
                text = None
        page = _soup(text or "", f"html:{rel}")
        if page:
            pages.append(page)
    if not pages:
        for rel in item.paths.get("har", []):
            main = main_entry(load_har(raw_dir / rel))
            if main is not None and main.body and "html" in main.mime:
                page = _soup(main.body.decode("utf-8", "replace"), f"har:{rel}")
                if page:
                    pages.append(page)
    return pages


def _structure_tokens(soup: BeautifulSoup) -> list[str]:
    body = soup.body or soup
    tokens: list[str] = []

    def walk(node: Tag, depth: int) -> None:
        for child in node.children:
            if not isinstance(child, Tag) or child.name in SKIP_STRUCTURE:
                continue
            tokens.append(f"{min(depth, MAX_DEPTH)}{child.name}")
            walk(child, depth + 1)

    walk(body, 0)
    return tokens


def simhash(tokens: list[str]) -> str | None:
    if len(tokens) < SHINGLE:
        return None
    counts: dict[str, int] = {}
    for i in range(len(tokens) - SHINGLE + 1):
        shingle = ">".join(tokens[i : i + SHINGLE])
        counts[shingle] = counts.get(shingle, 0) + 1
    vector = [0] * 64
    for shingle, weight in counts.items():
        digest = int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += weight if digest >> bit & 1 else -weight
    value = sum(1 << bit for bit in range(64) if vector[bit] > 0)
    return f"{value:016x}"


def _normalize_script(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\d{5,}", "N", text)
    return re.sub(r"[A-Za-z0-9_\-]{20,}", "T", text)


def _inline_scripts(soup: BeautifulSoup) -> list[str]:
    hashes = []
    for tag in soup.find_all("script"):
        if tag.get("src") or "json" in str(tag.get("type") or ""):
            continue
        body = tag.get_text()
        if len(body.strip()) < 40 or any(m in body.lower() for m in TRACKER_MARKERS):
            continue
        hashes.append(hashlib.sha1(_normalize_script(body).encode()).hexdigest()[:12])
    return hashes


def _script_names(soup: BeautifulSoup) -> list[str]:
    names = []
    for tag in soup.find_all("script", src=True):
        name = Path(urlsplit(str(tag["src"])).path).name.lower()
        name = VERSION_SUFFIX.sub("", name)
        if name and not GENERIC_SCRIPT.match(name):
            names.append(name)
    return names


def _css_classes(soup: BeautifulSoup) -> list[str]:
    seen: set[str] = set()
    for tag in soup.find_all(True):
        for cls in tag.get("class") or []:
            seen.add(cls)
        if tag.get("id"):
            seen.add(f"#{tag['id']}")
    return [c for c in seen if 3 <= len(c) <= 40 and not GENERIC_CLASS.match(c.lstrip("#"))]


def _asset_names(soup: BeautifulSoup, asset_dirs: list[Path]) -> list[str]:
    names: set[str] = set()
    for tag in soup.find_all("img", src=True):
        if not str(tag["src"]).startswith("data:"):
            names.add(Path(urlsplit(str(tag["src"])).path).name.lower())
    for directory in asset_dirs:
        try:
            files = sorted(directory.iterdir())[:MAX_ASSET_FILES]
        except OSError:
            continue
        names.update(f.name.lower() for f in files if f.suffix.lower() in IMAGE_SUFFIXES)
    return [
        n
        for n in names
        if n and Path(n).suffix in IMAGE_SUFFIXES and not HASHY_NAME.match(Path(n).stem)
    ]


def _form_fields(soup: BeautifulSoup) -> list[str]:
    fields: list[str] = []
    for form in soup.find_all("form"):
        for tag in form.find_all(["input", "select", "textarea"]):
            name = str(tag.get("name") or "").strip().lower()
            kind = str(tag.get("type") or tag.name).lower()
            if name and kind not in ("submit", "button"):
                fields.append(f"{'hidden' if kind == 'hidden' else 'field'}:{name}")
    names = {f.split(":", 1)[1] for f in fields}
    if len(names) < 3 or names <= GENERIC_FIELDS:
        return []
    return fields


def _comments(soup: BeautifulSoup) -> list[str]:
    hashes = []
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        text = re.sub(r"\s+", " ", str(node)).strip().lower()
        if len(text) < 8 or any(m in text for m in GENERIC_COMMENT_MARKERS):
            continue
        hashes.append(hashlib.sha1(_normalize_script(text).encode()).hexdigest()[:12])
    return hashes


def _meta(soup: BeautifulSoup) -> list[str]:
    values = []
    for tag in soup.find_all("meta"):
        key = str(tag.get("name") or tag.get("property") or "").lower()
        content = str(tag.get("content") or "").strip().lower()
        if key in META_KEYS and content:
            values.append(f"{key}:{content[:60]}")
    return values


def _asset_dirs(item: Item, raw_dir: Path) -> list[Path]:
    return [raw_dir / rel for rel in item.paths.get("assets", [])]


def extract(item: Item, raw_dir: Path) -> dict[str, Feature]:
    raw_dir = Path(raw_dir)
    pages = _load_pages(item, raw_dir)
    assets = _asset_dirs(item, raw_dir)
    reason = "brak pliku html i dokumentu HTML w HAR"
    values: dict[str, list[str] | str | None] = {name: None for name in NAMES}
    sources = "; ".join(p.source for p in pages[:3])
    if pages:
        tokens = [t for p in pages for t in _structure_tokens(p.soup)]
        values["template.dom_simhash"] = simhash(tokens)
        for name, fn in (
            ("template.inline_scripts", _inline_scripts),
            ("template.scripts", _script_names),
            ("template.css_classes", _css_classes),
            ("template.form_fields", _form_fields),
            ("template.html_comments", _comments),
            ("template.meta", _meta),
        ):
            merged = {v for p in pages for v in fn(p.soup)}
            values[name] = sorted(merged)[:MAX_ITEMS_PER_FEATURE]
        merged_assets = {n for p in pages for n in _asset_names(p.soup, assets)}
        values["template.asset_names"] = sorted(merged_assets)[:MAX_ITEMS_PER_FEATURE]
    elif assets:
        names = _asset_names(BeautifulSoup("", "lxml"), assets)
        values["template.asset_names"] = sorted(names)[:MAX_ITEMS_PER_FEATURE]
        sources = "zasoby: " + ", ".join(str(a.name)[:40] for a in assets[:2])
    features: dict[str, Feature] = {}
    for name in NAMES:
        value = values[name]
        if value:
            features[name] = Feature(name, GROUP, value, CONF, sources)
        else:
            features[name] = Feature.missing(name, GROUP, reason if not pages else "nie znaleziono")
    return features
