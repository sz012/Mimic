from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from engine.cluster.pipeline import extract_features
from engine.ingest import discover_items
from engine.store import Store


def main() -> int:
    raw = Path(os.environ.get("MIMIC_RAW_DIR") or "data/raw")
    cache = Path(os.environ.get("MIMIC_CACHE_DIR") or "data/cache")
    items = discover_items(raw)
    if not items:
        print(f"ingest: brak materiałów w {raw}")
        return 1
    store = Store()
    store.clear()
    kinds: Counter[str] = Counter()
    for item in items:
        extract_features(item, raw, cache)
        store.upsert_item(item)
        kinds.update(item.kinds)
    available = sum(1 for i in items for f in i.features.values() if f.available)
    total = sum(len(i.features) for i in items)
    print(f"materiały: {len(items)}, przypadki: {len({i.case_id for i in items})}")
    print("rodzaje:", ", ".join(f"{k}={n}" for k, n in sorted(kinds.items())))
    print(f"cechy dostępne: {available}/{total}")
    print(f"zapisano w {store.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
