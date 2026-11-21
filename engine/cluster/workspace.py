from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.cluster.campaigns import LINK_THRESHOLD, Campaign, Method, assign, cluster
from engine.cluster.pipeline import all_edges, extract_features
from engine.explain import assignment_card, campaign_card, edge_card
from engine.schema import Assignment, Edge, Item
from engine.similarity import Context, Weights, build_context, compare
from engine.similarity.compare import FORMULA
from engine.similarity.weights import DEFAULT

MIN_SIMILAR = 0.05


@dataclass
class Analysis:
    item: Item
    assignment: Assignment
    card: dict[str, Any]
    similar: list[dict[str, Any]]
    missing: list[dict[str, str]]
    available: list[str]
    formula: str = FORMULA

    @property
    def is_new_pattern(self) -> bool:
        return self.assignment.campaign_id is None


@dataclass
class Workspace:
    items: list[Item]
    raw_dir: Path
    cache_dir: Path | None = None
    threshold: float = LINK_THRESHOLD
    method: Method = "components"
    weights: Weights = field(default_factory=lambda: DEFAULT)
    edges: list[Edge] = field(default_factory=list)
    context: Context = field(default_factory=Context)
    campaigns: list[Campaign] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._index()
        self.context = build_context(self.items)
        self.edges = all_edges(self.items, self.context, self.weights)
        self.recluster()

    @classmethod
    def load(
        cls,
        items: list[Item],
        raw_dir: Path,
        cache_dir: Path | None = None,
        threshold: float = LINK_THRESHOLD,
        method: Method = "components",
        weights: Weights = DEFAULT,
    ) -> Workspace:
        ready = [extract_features(i, Path(raw_dir), cache_dir) for i in items]
        return cls(ready, Path(raw_dir), cache_dir, threshold, method, weights)

    def _index(self) -> None:
        self.by_id = {i.id: i for i in self.items}

    def recluster(
        self, threshold: float | None = None, method: Method | None = None
    ) -> list[Campaign]:
        if threshold is not None:
            self.threshold = threshold
        if method is not None:
            self.method = method
        self.campaigns = cluster(self.items, self.edges, self.threshold, self.method)
        self.label = {i.id: c.id for c in self.campaigns for i in c.items}
        return self.campaigns

    @property
    def real_campaigns(self) -> list[Campaign]:
        return [c for c in self.campaigns if not c.is_singleton]

    @property
    def singletons(self) -> list[Campaign]:
        return [c for c in self.campaigns if c.is_singleton]

    def campaign(self, campaign_id: str) -> Campaign | None:
        return next((c for c in self.campaigns if c.id == campaign_id), None)

    def prepare(self, item: Item, raw_dir: Path | None = None) -> Item:
        if item.features:
            return item
        return extract_features(
            item, Path(raw_dir or self.raw_dir), None if raw_dir else self.cache_dir
        )

    def analyze(self, item: Item, raw_dir: Path | None = None, limit: int = 10) -> Analysis:
        item = self.prepare(item, raw_dir)
        assignment = assign(item, self.campaigns, self.context, self.weights, self.threshold)
        similar = []
        for other in self.items:
            if other.id == item.id:
                continue
            edge = compare(item, other, self.context, self.weights)
            if edge is None or edge.score < MIN_SIMILAR:
                continue
            card = edge_card(edge)
            similar.append(
                {
                    "item": other.id,
                    "campaign": self.label.get(other.id),
                    "score": edge.score,
                    "card": card,
                    "edge": edge,
                }
            )
        similar.sort(key=lambda r: -r["score"])
        missing = [
            {"feature": f.name, "group": f.group, "reason": f.source}
            for f in sorted(item.features.values(), key=lambda f: f.name)
            if not f.available
        ]
        available = sorted(f.name for f in item.features.values() if f.available)
        return Analysis(
            item, assignment, assignment_card(assignment), similar[:limit], missing, available
        )

    def add(self, item: Item, raw_dir: Path | None = None) -> Assignment:
        item = self.prepare(item, raw_dir)
        assignment = assign(item, self.campaigns, self.context, self.weights, self.threshold)
        if item.id in self.by_id:
            return assignment
        self.items.append(item)
        self._index()
        self.context = build_context(self.items)
        for other in self.items[:-1]:
            edge = compare(other, item, self.context, self.weights)
            if edge is not None:
                self.edges.append(edge)
        self.recluster()
        if assignment.campaign_id is None:
            return assignment
        return Assignment(item.id, self.label[item.id], assignment.score, assignment.evidence)

    def campaign_cards(self, include_singletons: bool = False) -> list[dict[str, Any]]:
        chosen = self.campaigns if include_singletons else self.real_campaigns
        return [campaign_card(c.id, c.items, c.edges) for c in chosen]

    def card(self, campaign_id: str) -> dict[str, Any] | None:
        c = self.campaign(campaign_id)
        return campaign_card(c.id, c.items, c.edges) if c else None

    def graph(self, min_edge: float) -> dict[str, Any]:
        nodes = [
            {
                "id": i.id,
                "case": i.case_id,
                "campaign": self.label.get(i.id),
                "kinds": i.kinds,
                "singleton": self.campaign(self.label[i.id]).is_singleton,
            }
            for i in self.items
        ]
        links = [
            {
                "a": e.a,
                "b": e.b,
                "score": e.score,
                "linked": e.score >= self.threshold,
                "card": edge_card(e),
            }
            for e in self.edges
            if e.score >= min_edge
        ]
        return {"nodes": nodes, "links": links, "threshold": self.threshold}

    def stats(self) -> dict[str, int]:
        return {
            "items": len(self.items),
            "campaigns": len(self.real_campaigns),
            "singletons": len(self.singletons),
        }
