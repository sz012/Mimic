from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx

from engine.schema import Assignment, Edge, Item
from engine.schema import Campaign as SchemaCampaign
from engine.similarity import Context, Weights, compare
from engine.similarity.weights import DEFAULT

LINK_THRESHOLD = 0.6
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


def _components(ids: list[str], edges: list[Edge], threshold: float) -> list[set[str]]:
    g = nx.Graph()
    g.add_nodes_from(ids)
    g.add_edges_from((e.a, e.b) for e in edges if e.score >= threshold)
    return [set(c) for c in nx.connected_components(g)]


def _average_linkage(ids: list[str], edges: list[Edge], threshold: float) -> list[set[str]]:
    score = {(e.a, e.b): e.score for e in edges}
    score.update({(e.b, e.a): e.score for e in edges})
    clusters = [{i} for i in ids]

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
) -> list[Campaign]:
    ids = [i.id for i in items]
    by_id = {i.id: i for i in items}
    groups = (_average_linkage if method == "average" else _components)(ids, edges, threshold)
    groups.sort(key=lambda g: (-len(g), min(g)))
    campaigns = []
    for n, group in enumerate(groups, start=1):
        members = [by_id[i] for i in sorted(group)]
        inner = [e for e in edges if e.a in group and e.b in group and e.score >= threshold]
        prefix = "K" if len(members) > 1 else "N"
        campaigns.append(Campaign(id=f"{prefix}{n:02d}", items=members, edges=inner))
    return campaigns


def labels_of(campaigns: Iterable[Campaign]) -> dict[str, str]:
    return {item.id: c.id for c in campaigns for item in c.items}


def assign(
    item: Item,
    campaigns: Iterable[Campaign],
    context: Context | None = None,
    weights: Weights = DEFAULT,
    threshold: float = LINK_THRESHOLD,
) -> Assignment:
    best: tuple[float, Campaign | None, Edge | None] = (0.0, None, None)
    for campaign in campaigns:
        for member in campaign.items:
            if member.id == item.id:
                continue
            edge = compare(item, member, context, weights)
            if edge is not None and edge.score > best[0]:
                best = (edge.score, campaign, edge)
    score, campaign, edge = best
    evidence = edge.evidence if edge else []
    if campaign is None or score < threshold:
        return Assignment(
            item_id=item.id, campaign_id=None, score=round(score, 4), evidence=evidence
        )
    return Assignment(
        item_id=item.id, campaign_id=campaign.id, score=round(score, 4), evidence=evidence
    )
