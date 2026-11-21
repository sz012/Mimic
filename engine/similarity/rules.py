from __future__ import annotations

from dataclasses import dataclass

from engine.schema import Edge, Evidence

HARD_FEATURES = frozenset(
    {
        "text.exact",
        "visual.exact",
        "text.identifiers",
        "infra.tracker_ids",
        "infra.domain",
        "infra.cert_sans",
        "infra.url_params",
        "infra.favicon",
    }
)
LINK_THRESHOLD = 0.6
SUPPORTING = 0.08
HARD_MIN = 0.3
STRONG_SINGLE = 0.55
MIN_GROUPS = 2
GROUP_MIN = 0.25
NON_INDEPENDENT_GROUPS = frozenset({"person"})
WEAK_FEATURES = frozenset({"text.topic", "text.keywords", "text.prices"})


@dataclass(frozen=True)
class LinkBasis:
    ok: bool
    hard: tuple[str, ...]
    groups: tuple[str, ...]
    reason: str


def contribution(ev: Evidence) -> float:
    return ev.weight * ev.score


def link_basis(edge: Edge) -> LinkBasis:
    hard = tuple(
        sorted(
            {
                e.feature
                for e in edge.evidence
                if e.feature in HARD_FEATURES and contribution(e) >= HARD_MIN
            }
        )
    )
    groups = tuple(
        sorted(
            {
                e.group
                for e in edge.evidence
                if contribution(e) >= GROUP_MIN
                and e.group not in NON_INDEPENDENT_GROUPS
                and e.feature not in WEAK_FEATURES
            }
        )
    )
    if hard:
        return LinkBasis(True, hard, groups, "twarda przesłanka: " + ", ".join(hard))
    if len(groups) >= MIN_GROUPS:
        return LinkBasis(True, hard, groups, "niezależne grupy dowodów: " + ", ".join(groups))
    strongest = max(edge.evidence, key=contribution, default=None)
    if strongest is not None and contribution(strongest) >= STRONG_SINGLE:
        return LinkBasis(
            True,
            hard,
            groups,
            f"bardzo silna przesłanka w jednej grupie: {strongest.feature} ({contribution(strongest):.2f})",
        )
    if groups:
        return LinkBasis(
            False,
            hard,
            groups,
            f"istotne dowody tylko z jednej grupy ({groups[0]}), brak twardej przesłanki",
        )
    return LinkBasis(False, hard, groups, "brak istotnych przesłanek")


def is_link(edge: Edge, threshold: float) -> bool:
    return edge.score >= threshold and link_basis(edge).ok
