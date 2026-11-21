from __future__ import annotations

from collections import Counter
from typing import Any

from engine.schema import Assignment, Edge, Evidence, Item
from engine.similarity.compare import FORMULA

STRONG = 0.35
SUPPORTING = 0.08


def contribution(ev: Evidence) -> float:
    return ev.weight * ev.score


def reasons(evidence: list[Evidence], limit: int = 6) -> list[str]:
    ranked = sorted(
        (e for e in evidence if contribution(e) >= SUPPORTING), key=lambda e: -contribution(e)
    )
    return [f"{e.note} (wkład {contribution(e):.2f})" for e in ranked[:limit]]


def missing(evidence: list[Evidence]) -> list[str]:
    return [f"{e.feature}: {e.note}" for e in evidence if e.weight == 0.0]


def contrary(evidence: list[Evidence]) -> list[str]:
    return [f"{e.feature}: {e.note}" for e in evidence if e.weight >= 0.3 and e.score == 0.0]


def strength(score: float) -> str:
    if score >= 0.85:
        return "bardzo silne"
    if score >= 0.6:
        return "silne"
    if score >= 0.35:
        return "słabe"
    return "brak powiązania"


def edge_card(edge: Edge) -> dict[str, Any]:
    strong = [e for e in edge.evidence if contribution(e) >= STRONG]
    support = [e for e in edge.evidence if SUPPORTING <= contribution(e) < STRONG]
    if strong:
        summary = "połączone, bo: " + "; ".join(e.note.split(":")[0] for e in strong)
    elif support:
        summary = "tylko suma słabszych przesłanek: " + "; ".join(
            e.note.split(":")[0] for e in support[:4]
        )
    else:
        summary = "brak przesłanek"
    return {
        "a": edge.a,
        "b": edge.b,
        "score": edge.score,
        "strength": strength(edge.score),
        "summary": summary,
        "reasons": reasons(edge.evidence),
        "contrary": contrary(edge.evidence),
        "missing": missing(edge.evidence),
        "formula": FORMULA,
    }


def assignment_card(assignment: Assignment) -> dict[str, Any]:
    verdict = (
        f"przypisano do kampanii {assignment.campaign_id}"
        if assignment.campaign_id
        else "nowy wzorzec (brak kampanii powyżej progu)"
    )
    return {
        "item": assignment.item_id,
        "campaign": assignment.campaign_id,
        "score": assignment.score,
        "verdict": verdict,
        "reasons": reasons(assignment.evidence),
        "missing": missing(assignment.evidence),
    }


def shared_traits(
    items: list[Item], min_members: int = 2, limit: int = 8
) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, list[tuple[str, int]]] = {}
    for name in sorted({n for i in items for n in i.features}):
        counts: Counter[str] = Counter()
        for item in items:
            feat = item.features.get(name)
            if feat is None or not feat.available or not isinstance(feat.value, list):
                continue
            values = {v for v in feat.value if isinstance(v, str)}
            counts.update(values)
        common = [(v, c) for v, c in counts.most_common(limit) if c >= min_members]
        if common:
            out[name] = common
    return out


def campaign_card(campaign_id: str, items: list[Item], edges: list[Edge]) -> dict[str, Any]:
    feature_hits: Counter[str] = Counter()
    for e in edges:
        for ev in e.evidence:
            if contribution(ev) >= STRONG:
                feature_hits[ev.feature] += 1
    return {
        "id": campaign_id,
        "size": len(items),
        "members": [i.id for i in items],
        "cases": sorted({i.case_id for i in items}),
        "key_features": feature_hits.most_common(),
        "shared_traits": shared_traits(items),
        "edges": [edge_card(e) for e in sorted(edges, key=lambda e: -e.score)],
    }
