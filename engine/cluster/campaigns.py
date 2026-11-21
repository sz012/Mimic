from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx

from engine.schema import Assignment, Edge, Item
from engine.schema import Campaign as SchemaCampaign
from engine.similarity import Context, Weights, compare
from engine.similarity.rules import LINK_THRESHOLD, is_link, link_basis
from engine.similarity.weights import DEFAULT

MARGIN = 0.05
CASE_LINKS_DEFAULT = True
UPLOAD_CASE = "upload"
NON_CASE_IDS = frozenset({UPLOAD_CASE, "adlib"})
Method = Literal["components", "average"]


@dataclass
class Campaign:
    id: str
    items: list[Item]
    edges: list[Edge] = field(default_factory=list)

    @property
    def item_ids(self) -> list[str]:
        return [i.id for i in self.items]

    @property
    def members(self) -> list[str]:
        return self.item_ids

    def to_schema(self) -> SchemaCampaign:
        return SchemaCampaign(id=self.id, members=self.item_ids)

    @property
    def is_singleton(self) -> bool:
        return len(self.items) == 1


@dataclass
class AssignmentDetail:
    assignment: Assignment
    status: str
    basis: str
    runner_up: str | None = None
    runner_up_score: float = 0.0
    edge: Edge | None = None


def campaign_id(member_ids: Iterable[str]) -> str:
    ids = sorted(member_ids)
    return f"K-{ids[0]}" if len(ids) > 1 else f"N-{ids[0]}"


def case_pairs(items: list[Item]) -> list[tuple[str, str]]:
    by_case: dict[str, list[str]] = {}
    for item in items:
        if item.case_id and item.case_id not in NON_CASE_IDS:
            by_case.setdefault(item.case_id, []).append(item.id)
    return [(ids[0], other) for ids in by_case.values() for other in ids[1:]]


def _components(ids: list[str], links: list[Edge], extra: list[tuple[str, str]]) -> list[set[str]]:
    g = nx.Graph()
    g.add_nodes_from(ids)
    g.add_edges_from((e.a, e.b) for e in links)
    g.add_edges_from(extra)
    return [set(c) for c in nx.connected_components(g)]


def _average_linkage(
    ids: list[str], links: list[Edge], extra: list[tuple[str, str]], threshold: float
) -> list[set[str]]:
    score = {(e.a, e.b): e.score for e in links}
    score.update({(e.b, e.a): e.score for e in links})
    clusters = [{i} for i in ids]
    for a, b in extra:
        ca = next(c for c in clusters if a in c)
        cb = next(c for c in clusters if b in c)
        if ca is not cb:
            ca |= cb
            clusters.remove(cb)

    def link(x: set[str], y: set[str]) -> float:
        return sum(score.get((p, q), 0.0) for p in x for q in y) / (len(x) * len(y))

    while len(clusters) > 1:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                s = link(clusters[i], clusters[j])
                if best is None or s > best[0]:
                    best = (s, i, j)
        if best is None or best[0] < threshold:
            break
        _, i, j = best
        clusters[i] |= clusters.pop(j)
    return clusters


def cluster(
    items: list[Item],
    edges: list[Edge],
    threshold: float = LINK_THRESHOLD,
    method: Method = "components",
    case_links: bool = False,
    weights: Weights = DEFAULT,
) -> list[Campaign]:
    ids = [i.id for i in items]
    by_id = {i.id: i for i in items}
    links = [e for e in edges if is_link(e, threshold, weights.kit_as_campaign)]
    extra = case_pairs(items) if case_links else []
    if method == "average":
        groups = _average_linkage(ids, links, extra, threshold)
    else:
        groups = _components(ids, links, extra)
    groups.sort(key=lambda g: (-len(g), min(g)))
    campaigns = []
    for group in groups:
        members = [by_id[i] for i in sorted(group)]
        inner = [e for e in links if e.a in group and e.b in group]
        campaigns.append(Campaign(id=campaign_id(group), items=members, edges=inner))
    return campaigns


def labels_of(campaigns: Iterable[Campaign]) -> dict[str, str]:
    return {item.id: c.id for c in campaigns for item in c.items}


def _has_features(item: Item) -> bool:
    return any(f.available and f.value not in (None, [], {}) for f in item.features.values())


def assign_detail(
    item: Item,
    campaigns: Iterable[Campaign],
    context: Context | None = None,
    weights: Weights = DEFAULT,
    threshold: float = LINK_THRESHOLD,
    margin: float = MARGIN,
) -> AssignmentDetail:
    if not _has_features(item):
        return AssignmentDetail(
            Assignment(item.id, None, 0.0, []),
            "za_malo_danych",
            "materiał nie ma żadnej dostępnej cechy, nie da się go porównać",
        )
    ranked: list[tuple[float, bool, Campaign, Edge]] = []
    for campaign in campaigns:
        best: Edge | None = None
        qualified = False
        for member in campaign.items:
            if member.id == item.id:
                continue
            edge = compare(item, member, context, weights)
            if edge is None:
                continue
            ok = is_link(edge, threshold, weights.kit_as_campaign)
            if (ok, edge.score) > (qualified, best.score if best else -1.0):
                best, qualified = edge, ok
        if best is not None:
            ranked.append((best.score, qualified, campaign, best))
    ranked.sort(key=lambda r: (r[1], r[0]), reverse=True)
    if not ranked:
        return AssignmentDetail(
            Assignment(item.id, None, 0.0, []),
            "nowy_wzorzec",
            "brak wspólnych przesłanek z żadną kampanią",
        )
    score, qualified, campaign, edge = ranked[0]
    second = next(((s, q, c) for s, q, c, _ in ranked[1:] if q), None)
    if not qualified:
        reason = (
            link_basis(edge, weights.kit_as_campaign).reason
            if score >= threshold
            else f"najlepszy wynik {score:.2f} poniżej progu {threshold:.2f}"
        )
        return AssignmentDetail(
            Assignment(item.id, None, round(score, 4), edge.evidence),
            "nowy_wzorzec",
            reason,
            edge=edge,
        )
    basis = link_basis(edge, weights.kit_as_campaign).reason
    if second is not None and score - second[0] < margin:
        basis += f"; uwaga: pasuje także do {second[2].id} ({second[0]:.2f}), materiał może łączyć obie kampanie"
    return AssignmentDetail(
        Assignment(item.id, campaign.id, round(score, 4), edge.evidence),
        "przypisano",
        basis,
        runner_up=second[2].id if second else None,
        runner_up_score=round(second[0], 4) if second else 0.0,
        edge=edge,
    )


def assign(
    item: Item,
    campaigns: Iterable[Campaign],
    context: Context | None = None,
    weights: Weights = DEFAULT,
    threshold: float = LINK_THRESHOLD,
) -> Assignment:
    return assign_detail(item, campaigns, context, weights, threshold).assignment
