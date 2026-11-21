from __future__ import annotations

from engine.schema import Edge, Evidence, Feature, Item
from engine.similarity import comparators as cmp
from engine.similarity.context import Context
from engine.similarity.weights import DEFAULT, Weights

FORMULAS = {
    "features": "wynik = 1 - Π(1 - waga_i × zgodność_i) po cechach dostępnych po obu stronach; brak danych nie obniża wyniku",
    "groups": "wynik = 1 - Π(1 - max_g) po grupach cech, gdzie max_g to największy wkład (waga × zgodność) w grupie; brak danych nie obniża wyniku",
}
FORMULA = FORMULAS[DEFAULT.combine]


def formula(weights: Weights = DEFAULT) -> str:
    return FORMULAS[weights.combine]


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


def combine_groups(contributions: list[tuple[str, float]], mode: str = "features") -> float:
    if mode == "groups":
        best: dict[str, float] = {}
        for group, c in contributions:
            best[group] = max(best.get(group, 0.0), c)
        return combine(list(best.values()))
    return combine([c for _, c in contributions])


def compare(
    a: Item,
    b: Item,
    context: Context | None = None,
    weights: Weights = DEFAULT,
    min_score: float = 0.0,
) -> Edge | None:
    names = sorted(set(a.features) | set(b.features))
    evidence: list[Evidence] = []
    contributions: list[tuple[str, float]] = []
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
        elif name == "text.entities":
            res = spec.comparator(name, *_without_person_names(fa.value, fb.value, a, b), context)
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
        contributions.append((group, weight * res.score))
    if not contributions:
        return None
    score = round(combine_groups(contributions, weights.combine), 4)
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


def _person_tokens(item: Item) -> set[str]:
    feat = _available(item, "person.names")
    if feat is None:
        return set()
    out = set()
    for name in feat.value:
        low = str(name).lower()
        out.add(low)
        out.update(low.split())
    return out


def _without_person_names(va: list, vb: list, a: Item, b: Item) -> tuple[list, list]:
    names = _person_tokens(a) & _person_tokens(b)
    if not names:
        return va, vb

    def keep(v: str) -> bool:
        return not (
            v in names or any(v.startswith(n[: max(4, len(n) - 2)]) for n in names if len(n) > 4)
        )

    return [v for v in va if keep(v)], [v for v in vb if keep(v)]
