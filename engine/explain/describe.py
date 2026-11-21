from __future__ import annotations

from collections import Counter
from typing import Any

from engine.schema import Assignment, Edge, Evidence, Item
from engine.similarity.compare import combine_groups, formula
from engine.similarity.rules import HARD_FEATURES, LINK_THRESHOLD, LinkBasis, link_basis
from engine.similarity.weights import DEFAULT, Weights

STRONG = 0.35
SUPPORTING = 0.08

STATUS_VERDICT = {
    "przypisano": "przypisano do kampanii {campaign}",
    "nowy_wzorzec": "nowy wzorzec",
    "za_malo_danych": "za mało danych do porównania",
}


def contribution(ev: Evidence) -> float:
    return ev.weight * ev.score


def label(ev: Evidence) -> str:
    return ev.note.split(":")[0]


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


def _score_without(evidence: list[Evidence], removed: set[str], weights: Weights) -> float:
    return combine_groups(
        [
            (e.group, contribution(e))
            for e in evidence
            if e.feature not in removed and contribution(e) > 0
        ],
        weights.combine,
    )


def counterfactual(
    edge: Edge, basis: LinkBasis, linked: bool, threshold: float, weights: Weights
) -> str:
    ranked = sorted(
        (e for e in edge.evidence if contribution(e) > 0), key=lambda e: -contribution(e)
    )
    if linked:
        removed: set[str] = set()
        for ev in ranked:
            removed.add(ev.feature)
            rest = Edge(
                edge.a,
                edge.b,
                _score_without(edge.evidence, removed, weights),
                [e for e in edge.evidence if e.feature not in removed],
            )
            if rest.score < threshold or not link_basis(rest, weights.kit_as_campaign).ok:
                labels = [label(e) for e in ranked if e.feature in removed]
                names = ", ".join(labels[:4]) + (
                    f" i {len(labels) - 4} innych" if len(labels) > 4 else ""
                )
                return f"Rozdzieliłoby je usunięcie: {names} (wynik spadłby do {rest.score:.2f})."
        return "Połączenie nie zależy od pojedynczych przesłanek."
    if edge.score < threshold:
        need = 1 - (1 - threshold) / (1 - edge.score) if edge.score < 1 else 0.0
        hard = sorted(
            (f for f in HARD_FEATURES if weights.spec(f, f.split(".")[0]).weight >= need),
            key=lambda f: (-weights.spec(f, f.split(".")[0]).weight, f),
        )
        hint = f"; wystarczyłaby np. wspólna wartość {hard[0]}" if hard else ""
        return f"Do połączenia brakuje dodatkowego wkładu ≥ {need:.2f} (wynik {edge.score:.2f}, próg {threshold:.2f}){hint}."
    groups = ", ".join(basis.groups) or "brak"
    return (
        f"Wynik jest ponad progiem, ale dowody są tylko z grup: {groups}. "
        "Potrzebna twarda przesłanka albo dowód z innej grupy."
    )


def edge_card(
    edge: Edge, threshold: float = LINK_THRESHOLD, weights: Weights = DEFAULT
) -> dict[str, Any]:
    basis = link_basis(edge, weights.kit_as_campaign)
    linked = edge.score >= threshold and basis.ok
    strong = [e for e in edge.evidence if contribution(e) >= STRONG]
    support = [e for e in edge.evidence if SUPPORTING <= contribution(e) < STRONG]
    if strong:
        summary = "połączone, bo: " + "; ".join(label(e) for e in strong)
    elif support:
        summary = "tylko suma słabszych przesłanek: " + "; ".join(label(e) for e in support[:4])
    else:
        summary = "brak przesłanek"
    return {
        "a": edge.a,
        "b": edge.b,
        "score": edge.score,
        "strength": strength(edge.score),
        "linked": linked,
        "basis": basis.reason,
        "summary": summary,
        "reasons": reasons(edge.evidence),
        "contrary": contrary(edge.evidence),
        "missing": missing(edge.evidence),
        "counterfactual": counterfactual(edge, basis, linked, threshold, weights),
        "formula": formula(weights),
    }


def assignment_card(
    assignment: Assignment, status: str | None = None, basis: str = "", runner_up: str | None = None
) -> dict[str, Any]:
    status = status or ("przypisano" if assignment.campaign_id else "nowy_wzorzec")
    return {
        "item": assignment.item_id,
        "campaign": assignment.campaign_id,
        "score": assignment.score,
        "status": status,
        "verdict": STATUS_VERDICT[status].format(campaign=assignment.campaign_id),
        "basis": basis,
        "runner_up": runner_up,
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
            counts.update({v for v in feat.value if isinstance(v, str)})
        common = [(v, c) for v, c in counts.most_common(limit) if c >= min_members]
        if common:
            out[name] = common
    return out


def what_links(edges: list[Edge]) -> list[dict[str, Any]]:
    by_feature: dict[str, dict[str, Any]] = {}
    for e in edges:
        for ev in e.evidence:
            if contribution(ev) < SUPPORTING:
                continue
            row = by_feature.setdefault(
                ev.feature,
                {
                    "feature": ev.feature,
                    "group": ev.group,
                    "label": label(ev),
                    "edges": 0,
                    "strong": 0,
                    "best": 0.0,
                    "example": "",
                },
            )
            row["edges"] += 1
            row["strong"] += contribution(ev) >= STRONG
            if contribution(ev) > row["best"]:
                row["best"] = round(contribution(ev), 3)
                row["example"] = ev.note
    return sorted(by_feature.values(), key=lambda r: (-r["strong"], -r["edges"], -r["best"]))


def missing_data(items: list[Item]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        for name, feat in item.features.items():
            if feat.available:
                continue
            row = rows.setdefault(
                name, {"feature": name, "group": feat.group, "items": [], "reason": feat.source}
            )
            row["items"].append(item.id)
    return sorted(rows.values(), key=lambda r: (-len(r["items"]), r["feature"]))


def campaign_card(
    campaign_id: str,
    items: list[Item],
    edges: list[Edge],
    threshold: float = LINK_THRESHOLD,
    weights: Weights = DEFAULT,
) -> dict[str, Any]:
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
        "links": what_links(edges),
        "shared_traits": shared_traits(items),
        "missing": missing_data(items),
        "edges": [edge_card(e, threshold, weights) for e in sorted(edges, key=lambda e: -e.score)],
        "formula": formula(weights),
    }
