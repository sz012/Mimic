from __future__ import annotations

import html

from pyvis.network import Network

from engine.cluster import Campaign
from engine.explain import edge_card
from engine.schema import Edge, Item

PALETTE = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
    "#bcbd22",
]
SINGLE = "#9e9e9e"


def graph_html(
    items: list[Item],
    edges: list[Edge],
    campaigns: list[Campaign],
    min_edge: float,
    threshold: float,
) -> str:
    net = Network(height="620px", width="100%", cdn_resources="in_line", bgcolor="#ffffff")
    color = {}
    real = [c for c in campaigns if not c.is_singleton]
    for n, c in enumerate(real):
        for i in c.items:
            color[i.id] = PALETTE[n % len(PALETTE)]
    label = {i.id: c.id for c in campaigns for i in c.items}
    for item in items:
        net.add_node(
            item.id,
            label=item.id,
            title=f"{item.id}\nkampania: {label.get(item.id)}\nrodzaje: {', '.join(item.kinds)}",
            color=color.get(item.id, SINGLE),
        )
    for e in edges:
        if e.score < min_edge:
            continue
        card = edge_card(e)
        tip = f"{e.score:.2f}: {card['summary']}\n" + "\n".join(card["reasons"][:4])
        net.add_edge(
            e.a,
            e.b,
            value=e.score,
            title=html.escape(tip),
            color="#333333" if e.score >= threshold else "#cccccc",
            dashes=e.score < threshold,
        )
    net.toggle_physics(True)
    return net.generate_html()
