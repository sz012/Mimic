from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from engine.ingest import discover_items
from engine.schema import Item

LABELS_PATH = Path("data/labels/labels.json")


def check(labels: dict[str, str], items: list[Item]) -> tuple[list[str], list[str]]:
    ids = {i.id for i in items} | {i.case_id for i in items}
    unknown = sorted(key for key in labels if key not in ids)
    unlabeled = sorted(i.id for i in items if i.id not in labels and i.case_id not in labels)
    return unknown, unlabeled


def campaigns(labels: dict[str, str], items: list[Item]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in items:
        label = labels.get(item.id, labels.get(item.case_id))
        if label is not None:
            grouped[label].append(item.id)
    return dict(sorted(grouped.items()))


def main() -> int:
    path = Path(os.environ.get("MIMIC_LABELS") or LABELS_PATH)
    raw = Path(os.environ.get("MIMIC_RAW_DIR") or "data/raw")
    if not path.exists():
        print(f"labels: brak pliku {path}")
        return 1
    labels = json.loads(path.read_text(encoding="utf-8"))
    items = discover_items(raw)
    if not items:
        print(f"labels: brak materiałów w {raw}")
        return 1
    unknown, unlabeled = check(labels, items)
    for label, members in campaigns(labels, items).items():
        print(f"{label}: {', '.join(members)}")
    if unknown:
        print("nieznane identyfikatory w etykietach:", ", ".join(unknown))
    if unlabeled:
        print("materiały bez etykiety:", ", ".join(unlabeled))
    return 1 if unknown or unlabeled else 0


if __name__ == "__main__":
    sys.exit(main())
