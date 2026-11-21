from __future__ import annotations

from engine.features.text import minhash_signature
from engine.schema import Feature, Item


def _f(name: str, value, conf: float = 0.9) -> Feature:
    return Feature(name, name.split(".")[0], value, conf, "dane syntetyczne (demo)")


def _story(words: list[str], n: int = 60) -> dict:
    toks = (words * (n // len(words) + 1))[:n]
    return {"minhash": minhash_signature(toks), "tokens": n, "preview": " ".join(toks[:30])}


def demo_items() -> list[Item]:
    invest = [
        "platforma",
        "inwestycja",
        "zysk",
        "dzienny",
        "rejestracja",
        "bankier",
        "ujawnia",
        "sekret",
    ]
    health = [
        "kapsułki",
        "stawy",
        "lekarz",
        "kuracja",
        "promocja",
        "zamówienie",
        "ból",
        "naturalny",
    ]
    lottery = [
        "gratulacje",
        "wygrana",
        "nagroda",
        "losowanie",
        "odbierz",
        "telefon",
        "kurier",
        "dopłata",
    ]
    items = [
        Item(
            "demo/A1",
            "demoA",
            {"html": ["demo/A1/index.html"]},
            {
                "text.narrative": _f("text.narrative", _story(invest)),
                "text.title": _f("text.title", ["bankier", "sekret", "ujawnia"]),
                "person.names": _f("person.names", ["Jan Przykładowy"]),
                "visual.assets": _f(
                    "visual.assets", [{"src": "logo.png", "phash": "ff00ff00ff00ff00"}]
                ),
            },
        ),
        Item(
            "demo/A2",
            "demoA",
            {"html": ["demo/A2/index.html"]},
            {
                "text.narrative": _f("text.narrative", _story(invest[1:] + invest[:1])),
                "text.title": _f("text.title", ["bankier", "sekret", "zysk"]),
                "person.names": _f("person.names", ["Jan Przykładowy"]),
                "visual.assets": _f(
                    "visual.assets", [{"src": "logo-kopia.png", "phash": "ff00ff00ff00ff01"}]
                ),
            },
        ),
        Item(
            "demo/B1",
            "demoB",
            {"html": ["demo/B1/index.html"]},
            {
                "text.narrative": _f("text.narrative", _story(health)),
                "text.identifiers": _f("text.identifiers", ["phone:500600700"]),
                "text.title": _f("text.title", ["kapsułki", "stawy"]),
            },
        ),
        Item(
            "demo/B2",
            "demoB",
            {"screenshot": ["demo/B2/shot.png"]},
            {
                "text.identifiers": _f("text.identifiers", ["phone:500600700"]),
                "visual.screenshot": _f(
                    "visual.screenshot", [{"src": "shot.png", "phash": "0f0f0f0f0f0f0f0f"}]
                ),
            },
        ),
        Item(
            "demo/C1",
            "demoC",
            {"html": ["demo/C1/index.html"]},
            {
                "text.narrative": _f("text.narrative", _story(lottery)),
                "text.title": _f("text.title", ["wygrana", "nagroda"]),
            },
        ),
    ]
    return items
