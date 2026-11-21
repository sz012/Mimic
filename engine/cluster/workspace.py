from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.cluster.campaigns import (
    CASE_LINKS_DEFAULT,
    LINK_THRESHOLD,
    AssignmentDetail,
    Campaign,
    Method,
    assign_detail,
    cluster,
)
from engine.cluster.pipeline import all_edges, extract_all, extract_features, has_features
from engine.explain import assignment_card, campaign_card, edge_card
from engine.schema import Assignment, Edge, Item
from engine.similarity import Context, Weights, build_context, compare
from engine.similarity.compare import formula
from engine.similarity.weights import DEFAULT
from engine.sources.adlib import AdLibraryUnavailable, AdQuery, materialize, search
from engine.store import Store

MIN_SIMILAR = 0.05


@dataclass
class Analysis:
    item: Item
    assignment: Assignment
    card: dict[str, Any]
    similar: list[dict[str, Any]]
    missing: list[dict[str, str]]
    available: list[str]
    detail: AssignmentDetail
    formula: str = ""
    best_edge_card: dict[str, Any] | None = None

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
    case_links: bool = CASE_LINKS_DEFAULT
    store: Store | None = field(default=None, repr=False)

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
        store: Store | None = None,
    ) -> Workspace:
        fresh = [i for i in items if not i.features]
        prepared = [i for i in items if i.features]
        ready = extract_all(fresh, Path(raw_dir), cache_dir) + prepared
        known = {i.id for i in ready}
        stored = [i for i in store.items() if i.id not in known] if store else []
        if store:
            for item in ready:
                store.upsert_item(item)
        return cls(
            ready + stored, Path(raw_dir), cache_dir, threshold, method, weights, store=store
        )

    def _index(self) -> None:
        self.by_id = {i.id: i for i in self.items}

    def recluster(
        self,
        threshold: float | None = None,
        method: Method | None = None,
        case_links: bool | None = None,
    ) -> list[Campaign]:
        if threshold is not None:
            self.threshold = threshold
        if method is not None:
            self.method = method
        if case_links is not None:
            self.case_links = case_links
        self.campaigns = cluster(
            self.items, self.edges, self.threshold, self.method, self.case_links, self.weights
        )
        self.label = {i.id: c.id for c in self.campaigns for i in c.items}
        if self.store is not None:
            self.store.save_campaigns([c.to_schema() for c in self.campaigns])
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
        detail = self.assign_detail(item)
        similar = []
        for other in self.items:
            if other.id == item.id:
                continue
            edge = compare(item, other, self.context, self.weights)
            if edge is None or edge.score < MIN_SIMILAR:
                continue
            card = edge_card(edge, self.threshold, self.weights)
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
        card = assignment_card(detail.assignment, detail.status, detail.basis, detail.runner_up)
        return Analysis(
            item,
            detail.assignment,
            card,
            similar[:limit],
            missing,
            available,
            detail,
            formula(self.weights),
            edge_card(detail.edge, self.threshold, self.weights) if detail.edge else None,
        )

    def assign_detail(self, item: Item) -> AssignmentDetail:
        return assign_detail(item, self.campaigns, self.context, self.weights, self.threshold)

    def add(self, item: Item, raw_dir: Path | None = None) -> Assignment:
        item = self.prepare(item, raw_dir)
        assignment = self.assign_detail(item).assignment
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
        if assignment.campaign_id is not None:
            assignment = Assignment(
                item.id, self.label[item.id], assignment.score, assignment.evidence
            )
        if self.store is not None:
            self.store.upsert_item(item)
            self.store.save_assignment(assignment)
        return assignment

    def search_ads(
        self,
        terms: str,
        countries: list[str],
        root: Path,
        max_pages: int = 1,
        transport=None,
        access_token: str | None = None,
    ) -> tuple[list[tuple[Item, Analysis]], str | None]:
        try:
            ads = search(AdQuery(terms, countries, max_pages=max_pages), transport, access_token)
        except AdLibraryUnavailable as exc:
            return [], f"biblioteka reklam niedostępna: {exc}"
        results = []
        for item in materialize(ads, root):
            known = self.by_id.get(item.id)
            ready = known or extract_features(item, Path(root), None)
            results.append((ready, self.analyze(ready, Path(root))))
        return results, None

    def history(self) -> list[Assignment]:
        return self.store.assignments() if self.store is not None else []

    def campaign_cards(self, include_singletons: bool = False) -> list[dict[str, Any]]:
        chosen = self.campaigns if include_singletons else self.real_campaigns
        return [campaign_card(c.id, c.items, c.edges, self.threshold, self.weights) for c in chosen]

    def card(self, campaign_id: str) -> dict[str, Any] | None:
        c = self.campaign(campaign_id)
        return campaign_card(c.id, c.items, c.edges, self.threshold, self.weights) if c else None

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
                "linked": card["linked"],
                "card": card,
            }
            for e in self.edges
            if e.score >= min_edge
            for card in [edge_card(e, self.threshold, self.weights)]
        ]
        return {"nodes": nodes, "links": links, "threshold": self.threshold}

    def stats(self) -> dict[str, int]:
        return {
            "insufficient": sum(1 for i in self.items if not has_features(i)),
            "items": len(self.items),
            "campaigns": len(self.real_campaigns),
            "singletons": len(self.singletons),
        }
