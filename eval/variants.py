from __future__ import annotations

import copy
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import replace

from engine.cluster.campaigns import Method, assign_detail, cluster
from engine.cluster.pipeline import all_edges, has_features
from engine.schema import Feature, Item
from engine.similarity import Weights, build_context
from engine.similarity.rules import LINK_THRESHOLD
from engine.similarity.weights import DEFAULT

GROUPS = ("text", "visual", "person", "infra", "template")


EXACT = ("text.exact", "visual.exact")


def _with(item: Item, suffix: str, features: dict[str, Feature]) -> Item:
    if suffix != "duplikat":
        features = {k: v for k, v in features.items() if k not in EXACT}
    twin = copy.copy(item)
    twin.id = f"{item.id}#{suffix}"
    twin.case_id = f"{item.case_id}#{suffix}"
    twin.features = features
    return twin


def _drop_group(group: str) -> Callable[[Item, random.Random], Item]:
    def make(item: Item, rnd: random.Random) -> Item:
        return _with(
            item, f"bez_{group}", {k: v for k, v in item.features.items() if v.group != group}
        )

    return make


def _only_group(group: str) -> Callable[[Item, random.Random], Item]:
    def make(item: Item, rnd: random.Random) -> Item:
        return _with(
            item, f"tylko_{group}", {k: v for k, v in item.features.items() if v.group == group}
        )

    return make


def _thin(item: Item, rnd: random.Random) -> Item:
    out = {}
    for name, f in item.features.items():
        v = f.value
        if not f.available:
            out[name] = f
        elif isinstance(v, dict) and "minhash" in v:
            hv = [h if rnd.random() < 0.5 else rnd.getrandbits(32) for h in v["minhash"]]
            out[name] = replace(f, value={**v, "minhash": hv})
        elif isinstance(v, list) and len(v) > 1:
            keep = sorted(rnd.sample(range(len(v)), max(1, len(v) // 2)))
            out[name] = replace(f, value=[v[i] for i in keep])
        else:
            out[name] = f
    return _with(item, "okrojony", out)


def _duplicate(item: Item, rnd: random.Random) -> Item:
    return _with(item, "duplikat", dict(item.features))


def variant_makers(items: list[Item]) -> dict[str, Callable[[Item, random.Random], Item]]:
    present = {f.group for i in items for f in i.features.values() if f.available}
    makers: dict[str, Callable[[Item, random.Random], Item]] = {
        "duplikat": _duplicate,
        "okrojony": _thin,
    }
    for g in GROUPS:
        if g in present:
            makers[f"bez_{g}"] = _drop_group(g)
            makers[f"tylko_{g}"] = _only_group(g)
    return makers


def variants_report(
    items: list[Item],
    threshold: float = LINK_THRESHOLD,
    method: Method = "components",
    weights: Weights = DEFAULT,
    seed: int = 11,
) -> dict:
    rnd = random.Random(seed)
    ctx = build_context(items)
    campaigns = cluster(items, all_edges(items, ctx, weights), threshold, method, False, weights)
    home = {i.id: c for c in campaigns for i in c.items}
    stats: dict[str, Counter] = {}
    for kind, make in variant_makers(items).items():
        counter = stats.setdefault(kind, Counter())
        for item in items:
            if not has_features(item):
                continue
            variant = make(item, rnd)
            if not has_features(variant):
                counter["za_malo_danych"] += 1
                continue
            detail = assign_detail(variant, campaigns, ctx, weights, threshold)
            counter["razem"] += 1
            if detail.assignment.campaign_id == home[item.id].id:
                counter["do_oryginalu"] += 1
            elif detail.assignment.campaign_id is None:
                counter["nowy_wzorzec"] += 1
            else:
                counter["do_innej_kampanii"] += 1
    out = {}
    for kind, c in stats.items():
        total = c["razem"]
        out[kind] = {
            **dict(c),
            "odpornosc": round(c["do_oryginalu"] / total, 4) if total else None,
            "falszywe": c["do_innej_kampanii"],
        }
    return out
