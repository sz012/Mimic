from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.sources import load_items, raw_dir
from engine.cluster import LINK_THRESHOLD, cluster, labels_of
from engine.cluster.pipeline import all_edges, extract_features
from engine.schema import Item
from engine.similarity import Weights, build_context, compare
from eval.labels import label_files, load_truth
from eval.metrics import pair_report

THRESHOLDS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
GROUPS = ["text", "visual", "person", "infra", "template"]


def _without_group(items: list[Item], group: str) -> list[Item]:
    out = []
    for item in items:
        clone = copy.copy(item)
        clone.features = {k: v for k, v in item.features.items() if v.group != group}
        out.append(clone)
    return out


def duplicate_check(items: list[Item]) -> dict:
    failures = []
    for item in items:
        twin = copy.deepcopy(item)
        twin.id = item.id + "#dup"
        edge = compare(item, twin)
        if edge is None or edge.score < LINK_THRESHOLD:
            failures.append(item.id)
    return {"checked": len(items), "not_linked_to_own_copy": failures}


def evaluate(
    items: list[Item], truth: dict[str, str], threshold: float, method: str, weights: Weights
) -> dict:
    ctx = build_context(items)
    edges = all_edges(items, ctx, weights)
    sweep = {}
    for t in THRESHOLDS:
        rep = pair_report(truth, labels_of(cluster(items, edges, t, method)))
        sweep[str(t)] = {
            k: getattr(rep, k) for k in ("precision", "recall", "f1", "ari", "predicted_pairs")
        }
    main = pair_report(truth, labels_of(cluster(items, edges, threshold, method)))
    ablation = {}
    for group in GROUPS:
        if not any(f.group == group for i in items for f in i.features.values()):
            continue
        reduced = _without_group(items, group)
        e2 = all_edges(reduced, build_context(reduced), weights)
        rep = pair_report(truth, labels_of(cluster(reduced, e2, threshold, method)))
        ablation[f"bez_{group}"] = {
            k: getattr(rep, k) for k in ("precision", "recall", "f1", "ari")
        }
    edge_scores = {
        f"{e.a} | {e.b}": e.score for e in sorted(edges, key=lambda e: -e.score) if e.score >= 0.3
    }
    return {
        "main": asdict(main),
        "sweep": sweep,
        "ablation": ablation,
        "edges_over_0.3": edge_scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=LINK_THRESHOLD)
    parser.add_argument("--method", choices=["components", "average"], default="components")
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("data/cache/eval_report.json"))
    args = parser.parse_args(argv)

    root = raw_dir()
    items = [extract_features(i, root, Path("data/cache")) for i in load_items()]
    if not items:
        print(f"eval: brak materiałów w {root}")
        return 1
    files = [args.labels] if args.labels else label_files()
    truth = load_truth(items, files)
    print(
        f"materiały: {len(items)}, z etykietą: {len(truth)}, pliki etykiet: {[str(f) for f in files] or 'brak'}"
    )
    report = {"duplicates": duplicate_check(items)}
    if truth:
        report.update(evaluate(items, truth, args.threshold, args.method, Weights()))
        m = report["main"]
        print(
            f"próg {args.threshold} ({args.method}): precyzja {m['precision']}, pokrycie {m['recall']}, F1 {m['f1']}, ARI {m['ari']}"
        )
        print("test 'nie łącz' (fałszywe połączenia):", m["false_links"] or "brak")
        print("pominięte połączenia:", m["missed_links"] or "brak")
        print("próg  precyzja  pokrycie  F1    ARI")
        for t, r in report["sweep"].items():
            print(f"{t:<5} {r['precision']:<9} {r['recall']:<9} {r['f1']:<5} {r['ari']}")
        for name, r in report["ablation"].items():
            print(f"{name}: precyzja {r['precision']}, pokrycie {r['recall']}, F1 {r['f1']}")
    else:
        edges = all_edges(items)
        groups = [
            c.item_ids
            for c in cluster(items, edges, args.threshold, args.method)
            if not c.is_singleton
        ]
        print("brak etykiet: pokazuję tylko grupy:", groups)
        report["clusters"] = groups
    dup = report["duplicates"]
    print(
        f"duplikaty: {dup['checked'] - len(dup['not_linked_to_own_copy'])}/{dup['checked']} połączone z własną kopią"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"raport: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
