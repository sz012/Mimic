from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from engine.schema import Item
from engine.similarity.context import Context
from engine.similarity.weights import DEFAULT, Weights

MIN_KEY_WEIGHT = 0.4
LSH_ROWS = 4
HASH_SEGMENTS = 4
MAX_BUCKET = 200


def _hash_keys(name: str, value: str) -> list[str]:
    if len(value) % HASH_SEGMENTS:
        return [f"{name}={value}"]
    step = len(value) // HASH_SEGMENTS
    return [f"{name}#{i}={value[i * step : (i + 1) * step]}" for i in range(HASH_SEGMENTS)]


def item_keys(item: Item, context: Context | None = None, weights: Weights = DEFAULT) -> set[str]:
    keys: set[str] = set()
    for name, feat in item.features.items():
        if not feat.available or feat.value in (None, [], {}):
            continue
        value = feat.value
        if isinstance(value, dict) and "minhash" in value:
            hv = value["minhash"]
            for band in range(0, len(hv), LSH_ROWS):
                keys.add(f"{name}~{band}={hash(tuple(hv[band : band + LSH_ROWS]))}")
            continue
        if weights.spec(name, feat.group).weight < MIN_KEY_WEIGHT:
            continue
        if name == "person.face_vectors":
            keys.add("faces")
            continue
        if isinstance(value, str):
            keys.update(
                _hash_keys(name, value) if len(value) in (16, 32, 64) else [f"{name}={value}"]
            )
            continue
        if not isinstance(value, list):
            continue
        for v in value:
            if isinstance(v, dict) and "phash" in v:
                keys.update(_hash_keys("img", v["phash"]))
                if "top_phash" in v:
                    keys.update(_hash_keys("img", v["top_phash"]))
            elif isinstance(v, str) and not (context and context.is_common(name, v)):
                keys.add(f"{name}={v}")
    return keys


def candidate_pairs(
    items: list[Item], context: Context | None = None, weights: Weights = DEFAULT
) -> set[tuple[int, int]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for idx, item in enumerate(items):
        for key in item_keys(item, context, weights):
            buckets[key].append(idx)
    pairs: set[tuple[int, int]] = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > MAX_BUCKET:
            continue
        pairs.update(combinations(members, 2))
    return pairs
