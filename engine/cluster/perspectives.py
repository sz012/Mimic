from __future__ import annotations

from dataclasses import dataclass, field

from engine.cluster.campaigns import LINK_THRESHOLD, Campaign, cluster
from engine.cluster.pipeline import all_edges
from engine.schema import Edge, Item
from engine.similarity import Context, Weights, build_context
from engine.similarity.weights import DEFAULT

ALL_GROUPS = ("text", "visual", "infra", "template", "person")


@dataclass(frozen=True)
class Perspective:
    key: str
    label: str
    question: str
    groups: tuple[str, ...]
    kit_as_campaign: bool = False


PERSPECTIVES: dict[str, Perspective] = {
    p.key: p
    for p in (
        Perspective(
            "combined",
            "Łączona (domyślna)",
            "Czy materiały mają wspólne dowody z co najmniej dwóch niezależnych źródeł "
            "albo jeden twardy ślad?",
            ALL_GROUPS,
        ),
        Perspective(
            "operator",
            "Operator (infrastruktura)",
            "Czy za materiałami stoi ten sam operator: te same identyfikatory trackerów, "
            "konta reklamowe, domeny, certyfikaty, parametry kampanii w adresach?",
            ("infra",),
        ),
        Perspective(
            "template",
            "Szablon strony",
            "Czy strony zbudowano z tego samego szablonu: struktura DOM, klasy CSS, "
            "skrypty, pola formularzy?",
            ("template",),
        ),
        Perspective(
            "narrative",
            "Narracja (tekst)",
            "Czy materiały opowiadają tę samą historię: podobny tekst, kontakty, "
            "nazwy własne, kwoty?",
            ("text",),
        ),
        Perspective(
            "visual",
            "Wizerunek (obraz i osoby)",
            "Czy materiały używają tych samych obrazów, wyglądu strony i wizerunków "
            "osób publicznych?",
            ("visual", "person"),
        ),
        Perspective(
            "platform",
            "Platforma (zestaw narzędzi)",
            "Czy materiały korzystają z tego samego zestawu narzędzi: ta sama favicona "
            "i te same ścieżki formularzy? Takie grupy mogą łączyć różnych oszustów.",
            ("infra", "template"),
            kit_as_campaign=True,
        ),
    )
}
DEFAULT_PERSPECTIVE = "combined"


def perspective_weights(key: str, base: Weights = DEFAULT) -> Weights:
    p = PERSPECTIVES[key]
    scale = dict(base.scale)
    for group in ALL_GROUPS:
        if group not in p.groups:
            scale[group] = 0.0
    return Weights(
        features=dict(base.features),
        group_default=dict(base.group_default),
        scale=scale,
        combine=base.combine,
        kit_as_campaign=p.kit_as_campaign,
    )


def features_used(key: str, base: Weights = DEFAULT) -> list[tuple[str, float, str]]:
    p = PERSPECTIVES[key]
    w = perspective_weights(key, base)
    rows = []
    for name in sorted(w.features):
        group = name.split(".", 1)[0]
        if group in p.groups:
            spec = w.spec(name, group)
            rows.append((name, spec.weight, spec.label))
    return sorted(rows, key=lambda r: (-r[1], r[0]))


@dataclass
class PerspectiveResult:
    perspective: Perspective
    campaigns: list[Campaign]
    edges: list[Edge] = field(default_factory=list)

    @property
    def real(self) -> list[Campaign]:
        return [c for c in self.campaigns if not c.is_singleton]

    @property
    def singletons(self) -> list[Campaign]:
        return [c for c in self.campaigns if c.is_singleton]

    @property
    def label(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for c in self.campaigns:
            for item in c.items:
                out[item.id] = None if c.is_singleton else c.id
        return out


def run_perspective(
    items: list[Item],
    key: str,
    threshold: float = LINK_THRESHOLD,
    case_links: bool = False,
    context: Context | None = None,
    base: Weights = DEFAULT,
    method: str = "components",
) -> PerspectiveResult:
    weights = perspective_weights(key, base)
    edges = all_edges(items, context or build_context(items), weights)
    campaigns = cluster(items, edges, threshold, method, case_links, weights)
    return PerspectiveResult(PERSPECTIVES[key], campaigns, edges)


def run_all(
    items: list[Item],
    threshold: float = LINK_THRESHOLD,
    case_links: bool = False,
    base: Weights = DEFAULT,
    method: str = "components",
) -> dict[str, PerspectiveResult]:
    context = build_context(items)
    return {
        key: run_perspective(items, key, threshold, case_links, context, base, method)
        for key in PERSPECTIVES
    }


def membership_table(results: dict[str, PerspectiveResult], items: list[Item]) -> list[dict]:
    rows = []
    for item in items:
        row = {"materiał": item.id}
        for res in results.values():
            row[res.perspective.label] = res.label.get(item.id) or "-"
        rows.append(row)
    return rows
