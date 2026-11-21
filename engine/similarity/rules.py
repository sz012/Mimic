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
        "infra.ad_account",
        "infra.favicon",
    }
)
KIT_FEATURES = frozenset({"infra.favicon", "infra.endpoints"})
LINK_THRESHOLD = 0.6
SUPPORTING = 0.08
HARD_MIN = 0.3
STRONG_SINGLE = 0.55
MIN_GROUPS = 2
GROUP_MIN = 0.25
NON_INDEPENDENT_GROUPS = frozenset({"person"})
WEAK_FEATURES = frozenset(
    {
        "text.topic",
        "text.keywords",
        "text.prices",
        "infra.hosts",
        "infra.server",
        "infra.registrar",
        "template.meta",
    }
)


@dataclass(frozen=True)
class LinkBasis:
    ok: bool
    hard: tuple[str, ...]
    groups: tuple[str, ...]
    reason: str
    kit: tuple[str, ...] = ()


def contribution(ev: Evidence) -> float:
    return ev.weight * ev.score


def link_basis(edge: Edge, kit_as_campaign: bool = False) -> LinkBasis:
    kit = tuple(
        sorted(
            {
                e.feature
                for e in edge.evidence
                if e.feature in KIT_FEATURES and contribution(e) >= SUPPORTING
            }
        )
    )
    usable = [e for e in edge.evidence if kit_as_campaign or e.feature not in KIT_FEATURES]
    hard = tuple(
        sorted(
            {
                e.feature
                for e in usable
                if e.feature in HARD_FEATURES and contribution(e) >= HARD_MIN
            }
        )
    )
    groups = tuple(
        sorted(
            {
                e.group
                for e in usable
                if contribution(e) >= GROUP_MIN
                and e.group not in NON_INDEPENDENT_GROUPS
                and e.feature not in WEAK_FEATURES
            }
        )
    )
    kit_note = f"; wspólny zestaw narzędzi: {', '.join(kit)}" if kit and not kit_as_campaign else ""
    if hard:
        return LinkBasis(
            True, hard, groups, "twarda przesłanka: " + ", ".join(hard) + kit_note, kit
        )
    if len(groups) >= MIN_GROUPS:
        return LinkBasis(
            True, hard, groups, "niezależne grupy dowodów: " + ", ".join(groups) + kit_note, kit
        )
    strongest = max(usable, key=contribution, default=None)
    if strongest is not None and contribution(strongest) >= STRONG_SINGLE:
        return LinkBasis(
            True,
            hard,
            groups,
            f"bardzo silna przesłanka w jednej grupie: {strongest.feature} ({contribution(strongest):.2f}){kit_note}",
            kit,
        )
    if kit and not kit_as_campaign:
        return LinkBasis(
            False,
            hard,
            groups,
            f"tylko wspólny zestaw narzędzi ({', '.join(kit)}) bez dowodu z treści, szablonu lub identyfikatorów",
            kit,
        )
    if groups:
        return LinkBasis(
            False,
            hard,
            groups,
            f"istotne dowody tylko z jednej grupy ({groups[0]}), brak twardej przesłanki",
            kit,
        )
    return LinkBasis(False, hard, groups, "brak istotnych przesłanek", kit)


def is_link(edge: Edge, threshold: float, kit_as_campaign: bool = False) -> bool:
    return edge.score >= threshold and link_basis(edge, kit_as_campaign).ok
