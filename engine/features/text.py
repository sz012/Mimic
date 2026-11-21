from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from datasketch import MinHash

from engine.schema import Feature, Item

GROUP = "text"
NUM_PERM = 128
SHINGLE = 3
MAX_HTML_BYTES = 8_000_000
MAX_ENTITIES = 40

STOPWORDS = frozenset(
    {
        "a",
        "aby",
        "ale",
        "albo",
        "ani",
        "bardzo",
        "bez",
        "bo",
        "być",
        "był",
        "była",
        "było",
        "byli",
        "będzie",
        "co",
        "czy",
        "dla",
        "do",
        "gdy",
        "gdzie",
        "go",
        "i",
        "ich",
        "ile",
        "im",
        "inne",
        "jak",
        "jaki",
        "jako",
        "je",
        "jego",
        "jej",
        "jest",
        "jestem",
        "jeszcze",
        "już",
        "kiedy",
        "kto",
        "która",
        "które",
        "który",
        "której",
        "ma",
        "mają",
        "mam",
        "mi",
        "mnie",
        "może",
        "można",
        "mu",
        "na",
        "nad",
        "nam",
        "nas",
        "nie",
        "niż",
        "no",
        "nawet",
        "o",
        "od",
        "oraz",
        "po",
        "pod",
        "przed",
        "przez",
        "przy",
        "się",
        "są",
        "ta",
        "tak",
        "tam",
        "te",
        "tego",
        "tej",
        "ten",
        "też",
        "to",
        "tu",
        "tylko",
        "tym",
        "u",
        "w",
        "we",
        "według",
        "więc",
        "wszystko",
        "z",
        "za",
        "ze",
        "że",
        "żeby",
        "jednak",
        "będą",
        "by",
        "swoje",
        "swoją",
        "sobie",
        "teraz",
        "tutaj",
        "których",
        "również",
        "około",
        "został",
        "została",
        "zostało",
        "tych",
        "także",
        "wiele",
        "kilka",
        "czym",
        "czego",
        "mój",
        "moja",
        "moje",
        "twój",
        "nasz",
        "wasz",
        "ono",
        "one",
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "any",
        "can",
        "her",
        "was",
        "our",
        "out",
        "his",
        "has",
        "have",
        "had",
        "this",
        "that",
        "with",
        "from",
        "they",
        "will",
        "would",
        "there",
        "their",
        "what",
        "when",
        "which",
        "who",
        "your",
        "about",
        "into",
        "than",
        "then",
        "them",
        "these",
        "those",
        "more",
    }
)

TOPIC_LEXICON = {
    "investment": [
        "inwest",
        "zysk",
        "kapitał",
        "platform",
        "krypto",
        "bitcoin",
        "giełd",
        "zarab",
        "dochód",
        "trading",
        "algorytm",
        "portfel",
        "lokat",
        "akcj",
        "invest",
        "profit",
    ],
    "health": [
        "zdrow",
        "lekarz",
        "kuracj",
        "tablet",
        "kapsuł",
        "prostat",
        "cukrzyc",
        "stawy",
        "ciśnien",
        "odchudz",
        "suplement",
        "dawk",
        "leczen",
        "chorob",
        "pacjent",
        "aptek",
        "schorzen",
    ],
    "gambling": [
        "kasyn",
        "casino",
        "spin",
        "bonus",
        "jackpot",
        "slot",
        "zakład",
        "wygran",
        "bonanza",
    ],
    "shopping": ["sklep", "koszyk", "zamów", "dostaw", "promocj", "rabat", "cena", "przesyłk"],
    "news": [
        "redakcj",
        "wywiad",
        "dziennikar",
        "program",
        "emisj",
        "telewizj",
        "skandal",
        "sensacj",
        "nagrani",
        "studio",
        "prezenter",
    ],
}

WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
CAP_SEQ_RE = re.compile(
    r"\b([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}(?:[ -][A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}){1,3})\b"
)
CAP_WORD_RE = re.compile(r"(?<![.!?]\s)\b([A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,})\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?48[\s-]?)?(?:\d{3}[\s-]?\d{3}[\s-]?\d{3})(?!\d)")
HANDLE_RE = re.compile(
    r"(?:t\.me|telegram\.me|wa\.me|api\.whatsapp\.com/send\?phone=)/?([\w+]{4,})", re.IGNORECASE
)
IBAN_RE = re.compile(r"\bPL\s?\d{2}(?:\s?\d{4}){6}\b")
PRICE_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[ \u00a0.]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s?(zł|pln|€|eur|usd|\$)",
    re.IGNORECASE,
)


@dataclass
class TextDoc:
    source: str
    title: str = ""
    headings: list[str] = field(default_factory=list)
    narrative: str = ""
    full: str = ""
    links: list[str] = field(default_factory=list)


def tokens(text: str) -> list[str]:
    return [t for t in (w.lower() for w in WORD_RE.findall(text)) if t not in STOPWORDS]


def _read_bytes(path: Path, limit: int = MAX_HTML_BYTES) -> bytes:
    with path.open("rb") as fh:
        return fh.read(limit)


def parse_html(raw: bytes | str, source: str) -> TextDoc:
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()
    doc = TextDoc(source=source)
    title_tag = soup.find("title")
    og = soup.find("meta", attrs={"property": "og:title"})
    doc.title = (title_tag.get_text(" ", strip=True) if title_tag else "") or (
        og.get("content", "") if og else ""
    )
    doc.headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])][:40]
    blocks = []
    for el in soup.find_all(["p", "li", "blockquote", "h1", "h2", "h3"]):
        txt = el.get_text(" ", strip=True)
        if len(txt) >= 40:
            blocks.append(txt)
    doc.full = soup.get_text(" ", strip=True)
    doc.narrative = " ".join(dict.fromkeys(blocks))
    if len(tokens(doc.narrative)) < 30:
        doc.narrative = doc.full
    doc.links = [a.get("href", "") for a in soup.find_all("a") if a.get("href")]
    return doc


def _html_from_har(path: Path) -> bytes | None:
    try:
        har = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    best = None
    for entry in har.get("log", {}).get("entries", []):
        content = entry.get("response", {}).get("content", {})
        if "html" not in (content.get("mimeType") or ""):
            continue
        text = content.get("text")
        if not text:
            continue
        if content.get("encoding") == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8", "replace")
            except ValueError:
                continue
        if best is None or len(text) > len(best):
            best = text
    return best.encode("utf-8") if best else None


def _doc_from_meta(path: Path) -> TextDoc | None:
    try:
        meta = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    parts = [
        str(meta.get(k) or "") for k in ("title", "fulltitle", "description", "playlist_title")
    ]
    text = " ".join(dict.fromkeys(p for p in parts if p))
    if not text.strip():
        return None
    return TextDoc(
        source=f"{path.name}:title/description",
        title=str(meta.get("title") or ""),
        narrative=text,
        full=text,
    )


def load_docs(item: Item, raw_dir: Path) -> list[TextDoc]:
    docs: list[TextDoc] = []
    for rel in item.paths.get("html", []):
        path = raw_dir / rel
        try:
            docs.append(parse_html(_read_bytes(path), rel))
        except OSError:
            continue
    if not docs:
        for rel in item.paths.get("har", []):
            raw = _html_from_har(raw_dir / rel)
            if raw:
                docs.append(parse_html(raw, f"{rel}:response.content(text/html)"))
    for rel in item.paths.get("meta", []):
        doc = _doc_from_meta(raw_dir / rel)
        if doc:
            doc.source = f"{rel}:title/description"
            docs.append(doc)
    return docs


def minhash_signature(toks: list[str]) -> list[int]:
    mh = MinHash(num_perm=NUM_PERM)
    if len(toks) < SHINGLE:
        shingles = {" ".join(toks)}
    else:
        shingles = {" ".join(toks[i : i + SHINGLE]) for i in range(len(toks) - SHINGLE + 1)}
    for sh in shingles:
        mh.update(sh.encode("utf-8"))
    return [int(v) for v in mh.hashvalues]


def entities(text: str) -> list[str]:
    found: Counter[str] = Counter()
    for m in CAP_SEQ_RE.findall(text):
        found[m.lower()] += 2
    for m in CAP_WORD_RE.findall(text):
        low = m.lower()
        if low not in STOPWORDS:
            found[low] += 1
    return sorted(k for k, v in found.most_common(MAX_ENTITIES) if v >= 2)


def identifiers(text: str, links: list[str]) -> list[str]:
    blob = text + " " + " ".join(links)
    ids: set[str] = set()
    for e in EMAIL_RE.findall(blob):
        if not e.lower().endswith((".png", ".jpg", ".webp", ".gif", ".svg")):
            ids.add("email:" + e.lower())
    for link in links:
        if link.lower().startswith("tel:"):
            ids.add("phone:" + re.sub(r"\D", "", link)[-9:])
    for p in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", p)
        if len(digits) >= 9 and len(set(digits[-9:])) > 2:
            ids.add("phone:" + digits[-9:])
    for h in HANDLE_RE.findall(blob):
        ids.add("handle:" + h.lower())
    for iban in IBAN_RE.findall(text):
        ids.add("iban:" + re.sub(r"\s", "", iban))
    return sorted(ids)


def prices(text: str) -> list[str]:
    out = set()
    for amount, cur in PRICE_RE.findall(text):
        cur = {"pln": "zł", "eur": "€", "$": "usd"}.get(cur.lower(), cur.lower())
        amount = re.sub(r"[ \u00a0]", "", amount)
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", amount):
            amount = amount.replace(".", "")
        out.add(f"{amount.replace(',', '.')} {cur}")
    return sorted(out)


def topic(toks: list[str]) -> tuple[str | None, float]:
    scores = {
        name: sum(1 for t in toks for stem in stems if t.startswith(stem))
        for name, stems in TOPIC_LEXICON.items()
    }
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if scores[best] < 3 or total == 0:
        return None, 0.0
    return best, round(scores[best] / total, 3)


def top_keywords(toks: list[str], k: int = 30) -> list[str]:
    counts = Counter(t for t in toks if len(t) >= 4)
    return sorted(w for w, _ in counts.most_common(k))


def _conf(n: int, full: int) -> float:
    return round(min(1.0, n / full), 3)


def extract(item: Item, raw_dir: Path) -> dict[str, Feature]:
    docs = load_docs(item, Path(raw_dir))
    names = [
        "text.exact",
        "text.title",
        "text.narrative",
        "text.keywords",
        "text.entities",
        "text.identifiers",
        "text.prices",
        "text.topic",
    ]
    if not docs:
        return {n: Feature.missing(n, GROUP, "brak html/har/meta z tekstem") for n in names}
    source = ", ".join(d.source for d in docs)
    title = " ".join(d.title for d in docs if d.title)
    narrative = " ".join(d.narrative for d in docs)
    full = " ".join(d.full for d in docs)
    links = [link for d in docs for link in d.links]
    heading_text = " ".join(h for d in docs for h in d.headings)
    ntoks = tokens(narrative)
    feats: dict[str, Feature] = {}

    title_toks = sorted(set(tokens(title)))
    feats["text.title"] = (
        Feature("text.title", GROUP, title_toks, _conf(len(title_toks), 4), f"{source} <title>")
        if title_toks
        else Feature.missing("text.title", GROUP, f"{source} <title>")
    )
    feats["text.narrative"] = (
        Feature(
            "text.narrative",
            GROUP,
            {"minhash": minhash_signature(ntoks), "tokens": len(ntoks), "preview": narrative[:280]},
            _conf(len(ntoks), 150),
            f"{source} akapity <p>/<li>",
        )
        if len(ntoks) >= 15
        else Feature.missing("text.narrative", GROUP, f"{source} akapity <p>/<li>")
    )
    kw = top_keywords(ntoks)
    feats["text.keywords"] = (
        Feature("text.keywords", GROUP, kw, _conf(len(ntoks), 200), f"{source} częstość słów")
        if len(kw) >= 5
        else Feature.missing("text.keywords", GROUP, f"{source} częstość słów")
    )
    ents = entities(title + ". " + heading_text + ". " + narrative)
    feats["text.entities"] = (
        Feature("text.entities", GROUP, ents, _conf(len(ents), 5), f"{source} nazwy własne")
        if ents
        else Feature.missing("text.entities", GROUP, f"{source} nazwy własne")
    )
    ids = identifiers(full, links)
    feats["text.identifiers"] = (
        Feature("text.identifiers", GROUP, ids, 0.9, f"{source} e-mail/telefon/komunikator/IBAN")
        if ids
        else Feature.missing("text.identifiers", GROUP, f"{source} e-mail/telefon/komunikator/IBAN")
    )
    pr = prices(full)
    feats["text.prices"] = (
        Feature("text.prices", GROUP, pr, 0.6, f"{source} kwoty")
        if pr
        else Feature.missing("text.prices", GROUP, f"{source} kwoty")
    )
    exact_src = narrative if len(ntoks) >= 15 else title
    exact_toks = tokens(exact_src)
    feats["text.exact"] = (
        Feature(
            "text.exact",
            GROUP,
            [hashlib.sha1(" ".join(exact_toks).encode()).hexdigest()],
            1.0,
            f"{source} skrót znormalizowanego tekstu",
        )
        if len(exact_toks) >= 4
        else Feature.missing("text.exact", GROUP, f"{source} za mało tekstu")
    )
    tp, tconf = topic(tokens(full))
    feats["text.topic"] = (
        Feature("text.topic", GROUP, [tp], tconf, f"{source} słownik tematów")
        if tp
        else Feature.missing("text.topic", GROUP, f"{source} słownik tematów")
    )
    return feats
