from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from engine.schema import Item

COMMON_FRACTION = 0.5
MIN_ITEMS_FOR_COMMON = 6


@dataclass
class Context:
    n_items: int = 0
    df: dict[str, Counter] = field(default_factory=dict)

    def is_common(self, feature: str, value: str) -> bool:
        if self.n_items < MIN_ITEMS_FOR_COMMON:
            return False
        return self.df.get(feature, Counter()).get(value, 0) > COMMON_FRACTION * self.n_items


def value_keys(value) -> list[str]:
    if isinstance(value, list):
        keys = []
        for v in value:
            if isinstance(v, str):
                keys.append(v)
            elif isinstance(v, dict) and "phash" in v:
                keys.append(v["phash"])
        return keys
    if isinstance(value, str):
        return [value]
    return []


def build_context(items: list[Item]) -> Context:
    ctx = Context(n_items=len(items))
    for item in items:
        for name, feat in item.features.items():
            if not feat.available:
                continue
            keys = set(value_keys(feat.value))
            if keys:
                ctx.df.setdefault(name, Counter()).update(keys)
    return ctx
