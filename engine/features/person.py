from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from engine.features.text import load_docs
from engine.schema import Feature, Item

GROUP = "person"

REFERENCE_PERSONS = [
    "Rafał Brzoska",
    "Monika Olejnik",
    "Robert Lewandowski",
    "Anna Lewandowska",
    "Andrzej Duda",
    "Donald Tusk",
    "Mateusz Morawiecki",
    "Rafał Trzaskowski",
    "Szymon Hołownia",
    "Karol Nawrocki",
    "Sławomir Mentzen",
    "Jerzy Owsiak",
    "Kuba Wojewódzki",
    "Magda Gessler",
    "Marcin Prokop",
    "Dorota Wellman",
    "Krzysztof Stanowski",
    "Ewa Chodakowska",
    "Michał Sołowow",
    "Dominika Kulczyk",
    "Sebastian Kulczyk",
    "Zygmunt Solorz",
    "Leszek Czarnecki",
    "Iga Świątek",
    "Adam Małysz",
    "Marcin Gortat",
    "Tomasz Lis",
    "Piotr Kraśko",
    "Justyna Pochanke",
    "Bogdan Rymanowski",
    "Adam Glapiński",
    "Elon Musk",
    "Martyna Wojciechowska",
    "Agnieszka Chylińska",
    "Wojciech Cejrowski",
    "Grzegorz Hajdarowicz",
]


def _fold(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def _stem(word: str) -> str:
    word = _fold(word)
    return word[:-2] if len(word) > 6 else word[:-1] if len(word) > 4 else word


def _patterns() -> list[tuple[str, re.Pattern]]:
    out = []
    for name in REFERENCE_PERSONS:
        first, *rest = name.split()
        last = rest[-1]
        first_part = rf"{re.escape(_stem(first))}\w*\s+"
        optional = "" if len(last) <= 5 else "?"
        pat = re.compile(rf"\b(?:{first_part}){optional}{re.escape(_stem(last))}\w{{0,4}}\b")
        out.append((name, pat))
    return out


PATTERNS = _patterns()


def known_persons(text: str) -> dict[str, int]:
    folded = _fold(text)
    hits = {}
    for name, pat in PATTERNS:
        n = len(pat.findall(folded))
        if n:
            hits[name] = n
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
