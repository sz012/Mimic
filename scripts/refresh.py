from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from engine.cluster.campaigns import assign, cluster
from engine.cluster.pipeline import all_edges, extract_features
from engine.similarity import build_context
from engine.sources import AdLibraryUnavailable, AdQuery, materialize, search
from engine.store import Store

DEFAULT_INTERVAL = 6 * 3600


def _split(value: str | None) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def run_once(
    queries: list[str],
    countries: list[str],
    max_pages: int,
    store: Store,
    root: Path,
    cache: Path,
    transport=None,
) -> dict:
    known = {item.id for item in store.items()}
    fetched = []
    for terms in queries:
        fetched.extend(search(AdQuery(terms, countries, max_pages=max_pages), transport))
    new_items = [i for i in materialize(fetched, root) if i.id not in known]
    unique = {i.id: i for i in new_items}
    new_items = list(unique.values())
    before = store.items()
    old_campaigns = cluster(before, all_edges(before, build_context(before))) if before else []
    for item in new_items:
        extract_features(item, root, cache)
    context = build_context(before + new_items)
    assigned = 0
    for item in new_items:
        result = assign(item, old_campaigns, context)
        store.save_assignment(result)
        assigned += result.campaign_id is not None
    for item in new_items:
        store.upsert_item(item)
    everything = store.items()
    store.save_campaigns(
        [
            c.to_schema()
            for c in cluster(everything, all_edges(everything, build_context(everything)))
        ]
    )
    return {"fetched": len(fetched), "new": len(new_items), "assigned": assigned}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--country", action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=None)
    args = parser.parse_args(argv)
    queries = args.query or _split(os.environ.get("MIMIC_ADLIB_QUERIES"))
    countries = args.country or _split(os.environ.get("MIMIC_ADLIB_COUNTRIES")) or ["PL"]
    interval = args.interval or int(os.environ.get("MIMIC_REFRESH_SECONDS") or DEFAULT_INTERVAL)
    if not queries:
        print("refresh: podaj --query lub MIMIC_ADLIB_QUERIES")
        return 1
    store = Store()
    root = Path(os.environ.get("MIMIC_CACHE_DIR") or "data/cache") / "adlib"
    cache = Path(os.environ.get("MIMIC_CACHE_DIR") or "data/cache")
    while True:
        try:
            summary = run_once(queries, countries, args.max_pages, store, root, cache)
            print(
                f"refresh: pobrano {summary['fetched']}, nowych {summary['new']}, przypisanych {summary['assigned']}"
            )
        except AdLibraryUnavailable as exc:
            print(f"refresh: biblioteka reklam niedostępna ({exc})")
            if not args.loop:
                return 2
        if not args.loop:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
