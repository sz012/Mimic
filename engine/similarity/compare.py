from __future__ import annotations

from engine.schema import Edge, Evidence, Feature, Item
from engine.similarity import comparators as cmp
from engine.similarity.context import Context
from engine.similarity.weights import DEFAULT, Weights

FORMULA = "wynik = 1 - Π(1 - waga_i × zgodność_i) po cechach dostępnych po obu stronach; brak danych nie obniża wyniku"


def _available(item: Item, name: str) -> Feature | None:
    feat = item.features.get(name)
    return (
        feat if feat is not None and feat.available and feat.value not in (None, [], {}) else None
    )


def _missing_evidence(
    name: str, group: str, fa: Feature | None, fb: Feature | None, a: Item, b: Item
) -> Evidence:
    sides = []
    if fa is None:
        sides.append(a.id)
    if fb is None:
        sides.append(b.id)
    reason = next(
        (
            f.source
            for f in (a.features.get(name), b.features.get(name))
            if f is not None and not f.available
        ),
        "cecha nie została wyliczona",
    )
    return Evidence(
        name, group, 0.0, 0.0, None, None, f"brak danych ({', '.join(sides)}): {reason}"
    )


def combine(contributions: list[float]) -> float:
    remaining = 1.0
    for c in contributions:
        remaining *= 1.0 - max(0.0, min(0.99, c))
    return 1.0 - remaining


def compare(
    a: Item,
    b: Item,
    context: Context | None = None,
    weights: Weights = DEFAULT,
    min_score: float = 0.0,
) -> Edge | None:
    names = sorted(set(a.features) | set(b.features))
    evidence: list[Evidence] = []
    contributions: list[float] = []
    for name in names:
        group = (a.features.get(name) or b.features.get(name)).group
        fa, fb = _available(a, name), _available(b, name)
        if name == "visual.screenshot" and (fa or fb) and not (fa and fb):
            fa, fb = _screenshot_fallback(a, b, fa, fb)
        if fa is None or fb is None:
            evidence.append(_missing_evidence(name, group, fa, fb, a, b))
            continue
        spec = weights.spec(name, group)
        if name == "visual.screenshot":
            res = cmp.screenshot(
                name, fa.value, fb.value, context, _extra_images(a), _extra_images(b)
            )
        else:
            res = spec.comparator(name, fa.value, fb.value, context)
        confidence = min(fa.confidence, fb.confidence) if fa.confidence and fb.confidence else 1.0
        weight = round(spec.weight * (0.5 + 0.5 * confidence), 4)
        evidence.append(
            Evidence(
                name,
                group,
                weight,
                round(res.score, 4),
                res.left,
                res.right,
                f"{spec.label}: {res.note}",
            )
        )
        contributions.append(weight * res.score)
    if not contributions:
        return None
    score = round(combine(contributions), 4)
    if score <= min_score:
        return None
    evidence.sort(key=lambda e: (-(e.weight * e.score), e.weight == 0.0, e.feature))
    return Edge(a=a.id, b=b.id, score=score, evidence=evidence)


def _extra_images(item: Item) -> list[dict]:
    out = []
    for name in ("visual.assets", "visual.video"):
        feat = _available(item, name)
        if feat:
            out.extend(feat.value)
    return out


def _screenshot_fallback(a: Item, b: Item, fa: Feature | None, fb: Feature | None):
    if fa is None and _extra_images(a):
        fa = Feature(
            "visual.screenshot", "visual", [], fb.confidence, "zasoby jako zastępstwo zrzutu"
        )
    if fb is None and _extra_images(b):
        fb = Feature(
            "visual.screenshot", "visual", [], fa.confidence, "zasoby jako zastępstwo zrzutu"
        )
    return fa, fb
