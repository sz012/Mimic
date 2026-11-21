from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from engine.schema import Item

ID_KEYS = ("item_id", "case_id", "id", "case")
LABEL_KEYS = ("campaign", "campaign_id", "label", "kampania")


def label_files() -> list[Path]:
    override = os.environ.get("MIMIC_LABELS")
    if override:
        return [Path(override)]
    root = Path("data/labels")
    return (
        sorted(p for p in root.glob("*") if p.suffix.lower() in (".csv", ".json"))
        if root.exists()
        else []
    )


def _rows(path: Path) -> list[tuple[str, str]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return [(str(k), str(v)) for k, v in data.items()]
        return [
            (str(r[k]), str(r[l]))
            for r in data
            for k in ID_KEYS
            if k in r
            for l in LABEL_KEYS
            if l in r
        ]
    out = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = next((row[k] for k in ID_KEYS if row.get(k)), None)
            label = next((row[k] for k in LABEL_KEYS if row.get(k)), None)
            if key and label:
                out.append((key.strip(), label.strip()))
    return out


def load_truth(items: list[Item], paths: list[Path] | None = None) -> dict[str, str]:
    raw: dict[str, str] = {}
    for path in paths if paths is not None else label_files():
        raw.update(_rows(path))
    truth = {}
    for item in items:
        if item.id in raw:
            truth[item.id] = raw[item.id]
        elif item.case_id in raw:
            truth[item.id] = raw[item.case_id]
    return truth
