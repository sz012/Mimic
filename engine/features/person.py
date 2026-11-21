from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from engine.features.text import load_docs
from engine.schema import Feature, Item

GROUP = "person"
VERSION = "2"

REFS_FILE = Path(__file__).resolve().parents[2] / "data" / "refs" / "persons.json"


def reference_persons(path: Path = REFS_FILE) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in data.get("persons", []) if isinstance(p, dict) and p.get("name")]


def _fold(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def _stem(word: str) -> str:
    word = _fold(word)
    return word[:-2] if len(word) > 6 else word[:-1] if len(word) > 4 else word


def _pattern(full: str) -> re.Pattern:
    first, *rest = full.split()
    last = rest[-1] if rest else first
    if not rest:
        return re.compile(rf"\b{re.escape(_stem(first))}\w{{0,4}}\b")
    first_part = rf"{re.escape(_stem(first))}\w*?\s*"
    optional = "" if len(last) <= 5 else "?"
    return re.compile(rf"\b(?:{first_part}){optional}{re.escape(_stem(last))}\w{{0,4}}\b")


def _patterns() -> list[tuple[str, re.Pattern]]:
    out = []
    for person in reference_persons():
        for variant in [person["name"], *person.get("aliases", [])]:
            out.append((person["name"], _pattern(variant)))
    return out


PATTERNS = _patterns()


def known_persons(text: str) -> dict[str, int]:
    folded = _fold(text)
    hits = {}
    for name, pat in PATTERNS:
        n = len(pat.findall(folded))
        if n:
            hits[name] = hits.get(name, 0) + n
    return hits


def extract(item: Item, raw_dir: Path) -> dict[str, Feature]:
    docs = load_docs(item, Path(raw_dir))
    feats: dict[str, Feature] = {}
    if not docs:
        feats["person.names"] = Feature.missing(
            "person.names", GROUP, "brak tekstu do wyszukania osób"
        )
    else:
        text = " ".join(f"{d.title} {d.title} {d.full}" for d in docs)
        hits = known_persons(text)
        source = ", ".join(d.source for d in docs) + " vs baza referencyjna osób publicznych"
        names = sorted(n for n, c in hits.items() if c >= 2)
        feats["person.names"] = (
            Feature(
                "person.names",
                GROUP,
                names,
                round(min(1.0, max(hits[n] for n in names) / 5), 3),
                source,
            )
            if names
            else Feature.missing("person.names", GROUP, source)
        )
    feats["person.faces"] = Feature.missing(
        "person.faces",
        GROUP,
        "dopasowanie twarzy wymaga opcjonalnej zależności insightface (extra 'faces')",
    )
    return feats
