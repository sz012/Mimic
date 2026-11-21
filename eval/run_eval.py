from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.sources import load_items, raw_dir
from engine.cluster import LINK_THRESHOLD, cluster, labels_of
from engine.cluster.pipeline import all_edges, extract_all, has_features
from engine.schema import Item
from engine.similarity import Weights, build_context, compare
from engine.similarity.rules import is_link
from eval.holdout import holdout
from eval.labels import label_files, load_truth
from eval.metrics import pair_report
from eval.synthetic import synthetic_corpus
from eval.variants import variants_report

THRESHOLDS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
GROUPS = ["text", "visual", "person", "infra", "template"]
CONFIGS = {
    "cechy": {"combine": "features", "case_links": False},
    "grupy": {"combine": "groups", "case_links": False},
    "cechy+przypadek": {"combine": "features", "case_links": True},
    "grupy+przypadek": {"combine": "groups", "case_links": True},
}


def _without_group(items: list[Item], group: str) -> list[Item]:
    out = []
    for item in items:
        clone = copy.copy(item)
        clone.features = {k: v for k, v in item.features.items() if v.group != group}
        out.append(clone)
    return out


def duplicate_check(
    items: list[Item], threshold: float = LINK_THRESHOLD, weights: Weights | None = None
) -> dict:
    weights = weights or Weights()
    featured = [i for i in items if has_features(i)]
    failures = []
    for item in featured:
        twin = copy.deepcopy(item)
        twin.id = item.id + "#dup"
        edge = compare(item, twin, None, weights)
        if edge is None or not is_link(edge, threshold):
            failures.append(item.id)
    return {
        "checked": len(featured),
        "insufficient": [i.id for i in items if not has_features(i)],
        "not_linked_to_own_copy": failures,
        "rate": round(1 - len(failures) / len(featured), 4) if featured else 1.0,
    }


def _pairs(items, truth, edges, threshold, method, case_links) -> dict:
    rep = pair_report(truth, labels_of(cluster(items, edges, threshold, method, case_links)))
    return {k: getattr(rep, k) for k in ("precision", "recall", "f1", "ari", "predicted_pairs")}


def evaluate(items: list[Item], truth: dict[str, str], threshold: float, method: str) -> dict:
    configs = {}
    for name, cfg in CONFIGS.items():
        w = Weights(combine=cfg["combine"])
        edges = all_edges(items, build_context(items), w)
        main = pair_report(
            truth, labels_of(cluster(items, edges, threshold, method, cfg["case_links"]))
        )
        configs[name] = {
            "pairs": {
                k: getattr(main, k) for k in ("precision", "recall", "f1", "ari", "predicted_pairs")
            },
            "false_links": main.false_links,
            "missed_links": main.missed_links,
            "sweep": {
                str(t): _pairs(items, truth, edges, t, method, cfg["case_links"])
                for t in THRESHOLDS
            },
            "holdout": holdout(items, truth, threshold, method, w, cfg["case_links"]).summary(),
        }
    ablation = {}
    for group in GROUPS:
        if not any(f.group == group and f.available for i in items for f in i.features.values()):
            continue
        reduced = _without_group(items, group)
        e2 = all_edges(reduced, build_context(reduced))
        ablation[f"bez_{group}"] = _pairs(reduced, truth, e2, threshold, method, False)
    return {"configs": configs, "ablation": ablation}


def synthetic_section(threshold: float, method: str) -> dict:
    out = {}
    for decoys in (True, False):
        items, truth = synthetic_corpus(decoys=decoys)
        name = "z_wabikami" if decoys else "czysty"
        out[name] = {}
        for cfg_name in ("cechy", "grupy"):
            w = Weights(combine=CONFIGS[cfg_name]["combine"])
            edges = all_edges(items, build_context(items), w)
            out[name][cfg_name] = {
                "pairs": _pairs(items, truth, edges, threshold, method, False),
                "holdout": holdout(items, truth, threshold, method, w).summary(),
            }
        out[name]["warianty"] = variants_report(items, threshold, method)
    return out


def _print_summary(report: dict, threshold: float) -> None:
    syn = report["synthetic"]
    for name, sec in syn.items():
        for cfg in ("cechy", "grupy"):
            p, h = sec[cfg]["pairs"], sec[cfg]["holdout"]
            print(
                f"syntetyczny {name:<10} {cfg:<6} pary: P {p['precision']} R {p['recall']} ARI {p['ari']} | "
                f"holdout: trafność {h['accuracy']}, precyzja przypisań {h['assign_precision']}, "
                f"nowe wzorce {h['new_pattern_recall']}, fałszywe {h['false_assignments']}"
            )
    real = report.get("real")
    if real and "configs" in real:
        for name, cfg in real["configs"].items():
            p, h = cfg["pairs"], cfg["holdout"]
            print(
                f"dane {name:<16} pary: P {p['precision']} R {p['recall']} ARI {p['ari']} | "
                f"holdout: trafność {h['accuracy']}, fałszywe przypisania {h['false_assignments']}"
            )
            print("  test 'nie łącz' (fałszywe połączenia):", cfg["false_links"] or "brak")
        for name, r in real["ablation"].items():
            print(f"  {name}: P {r['precision']} R {r['recall']} F1 {r['f1']}")
    elif real:
        print("dane: brak etykiet, grupy przy progu", threshold, real["clusters"])
    for kind, r in report["variants_real"].items():
        print(
            f"warianty {kind:<14} odporność {r['odpornosc']}, fałszywe {r['falszywe']}, za mało danych {r.get('za_malo_danych', 0)}"
        )
    dup = report["duplicates"]
    print(
        f"duplikaty: {dup['checked'] - len(dup['not_linked_to_own_copy'])}/{dup['checked']} materiałów z cechami "
        f"połączonych z własną kopią; bez cech: {len(dup['insufficient'])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=LINK_THRESHOLD)
    parser.add_argument("--method", choices=["components", "average"], default="components")
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(os.environ.get("MIMIC_CACHE_DIR", "data/cache")) / "eval_report.json",
    )
    args = parser.parse_args(argv)

    root = raw_dir()
    items = extract_all(load_items(), root, Path(os.environ.get("MIMIC_CACHE_DIR", "data/cache")))
    files = [args.labels] if args.labels else label_files()
    truth = load_truth(items, files) if items else {}
    print(
        f"materiały: {len(items)}, z etykietą: {len(truth)}, pliki etykiet: {[str(f) for f in files] or 'brak'}"
    )
    report: dict = {"threshold": args.threshold, "method": args.method}
    report["synthetic"] = synthetic_section(args.threshold, args.method)
    report["duplicates"] = duplicate_check(items, args.threshold)
    report["variants_real"] = variants_report(items, args.threshold, args.method) if items else {}
    if truth:
        report["real"] = evaluate(items, truth, args.threshold, args.method)
    elif items:
        edges = all_edges(items)
        report["real"] = {
            "clusters": [
                c.item_ids
                for c in cluster(items, edges, args.threshold, args.method)
                if not c.is_singleton
            ]
        }
    _print_summary(report, args.threshold)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"raport: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
