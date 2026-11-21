from __future__ import annotations

import csv
import io
import json
from html import escape
from typing import Any

from engine.schema import Item

SKIPPED_FEATURES = {"person.face_vectors"}
VALUE_LIMIT = 240


def to_json(cards: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    return json.dumps({"meta": meta, "campaigns": cards}, ensure_ascii=False, indent=2, default=str)


def to_csv(cards: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["kampania", "material", "przypadek", "najsilniejsze_polaczenie", "wynik", "przeslanki"]
    )
    for card in cards:
        best: dict[str, dict[str, Any]] = {}
        for edge in card["edges"]:
            for side in (edge["a"], edge["b"]):
                if side not in best or edge["score"] > best[side]["score"]:
                    best[side] = edge
        for member in card["members"]:
            edge = best.get(member)
            other = (edge["b"] if edge["a"] == member else edge["a"]) if edge else ""
            writer.writerow(
                [
                    card["id"],
                    member,
                    member.split("/")[0],
                    other,
                    f"{edge['score']:.3f}" if edge else "",
                    edge["summary"] if edge else "brak połączeń (pojedynczy wzorzec)",
                ]
            )
    return buf.getvalue()


def _value_text(value: Any) -> str:
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "minhash"}
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= VALUE_LIMIT else text[: VALUE_LIMIT - 1] + "…"


def dataset_rows(items: list[Item], labels: dict[str, str | None]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        for feature in sorted(item.features.values(), key=lambda f: (f.group, f.name)):
            if feature.name in SKIPPED_FEATURES:
                continue
            rows.append(
                {
                    "material": item.id,
                    "przypadek": item.case_id,
                    "kampania": labels.get(item.id) or "",
                    "grupa": feature.group,
                    "cecha": feature.name,
                    "dostepna": feature.available,
                    "pewnosc": feature.confidence,
                    "zrodlo": feature.source,
                    "wartosc": _value_text(feature.value) if feature.available else "",
                }
            )
    return rows


def to_dataset_json(items: list[Item], labels: dict[str, str | None]) -> str:
    return json.dumps(dataset_rows(items, labels), ensure_ascii=False, indent=2)


def to_dataset_csv(items: list[Item], labels: dict[str, str | None]) -> str:
    rows = dataset_rows(items, labels)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "material",
            "przypadek",
            "kampania",
            "grupa",
            "cecha",
            "dostepna",
            "pewnosc",
            "zrodlo",
            "wartosc",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _list(items: list[str]) -> str:
    return (
        "<ul>" + "".join(f"<li>{escape(str(i))}</li>" for i in items) + "</ul>"
        if items
        else "<p>brak</p>"
    )


def to_html(cards: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    parts = [
        "<!doctype html><html lang='pl'><head><meta charset='utf-8'><title>Mimic: raport kampanii</title>",
        (
            "<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#111}"
            "h2{border-bottom:1px solid #ccc;padding-bottom:4px}table{border-collapse:collapse;width:100%;font-size:13px}"
            "td,th{border:1px solid #ddd;padding:4px 6px;text-align:left;vertical-align:top}.muted{color:#666;font-size:13px}"
            "@media print{h2{page-break-before:always}}</style></head><body>"
        ),
        "<h1>Raport kampanii</h1>",
        (
            f"<p class='muted'>Materiały: {escape(str(meta.get('items')))}, kampanie: {escape(str(meta.get('campaigns')))}, "
            f"próg połączenia: {escape(str(meta.get('threshold')))}, grupowanie: {escape(str(meta.get('method')))}</p>"
        ),
        f"<p class='muted'>{escape(str(meta.get('formula', '')))}</p>",
    ]
    for card in cards:
        parts.append(f"<h2>Kampania {escape(card['id'])} ({card['size']} materiałów)</h2>")
        parts.append("<p><b>Członkowie:</b> " + escape(", ".join(card["members"])) + "</p>")
        parts.append(
            "<h3>Co je łączy</h3><table><tr><th>Przesłanka</th><th>Połączeń</th><th>Mocnych</th><th>Przykład</th></tr>"
        )
        for row in card.get("links", []):
            parts.append(
                f"<tr><td>{escape(row['label'])}</td><td>{row['edges']}</td><td>{row['strong']}</td><td>{escape(row['example'])}</td></tr>"
            )
        parts.append("</table><h3>Połączenia</h3>")
        for edge in card["edges"]:
            parts.append(
                f"<p><b>{escape(edge['a'])} ↔ {escape(edge['b'])}</b>: {edge['score']:.2f} ({escape(edge['strength'])}). {escape(edge['summary'])}</p>"
            )
            parts.append(_list(edge["reasons"]))
        missing = [
            f"{m['feature']}: {len(m['items'])} z {card['size']} ({m['reason']})"
            for m in card.get("missing", [])
        ]
        parts.append("<h3>Brakujące dane</h3>" + _list(missing))
    parts.append("</body></html>")
    return "".join(parts)
