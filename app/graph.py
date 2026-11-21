from __future__ import annotations

from html import escape
from typing import Any

from pyvis.network import Network

from app.brand import Brand


def _safe(text: str) -> str:
    return escape(text).replace("\n", " ")


def graph_html(graph: dict[str, Any], brand: Brand) -> str:
    net = Network(height="620px", width="100%", cdn_resources="in_line", bgcolor="#ffffff")
    order = sorted({n["campaign"] for n in graph["nodes"] if not n["singleton"]})
    color = {cid: brand.campaign_color(i) for i, cid in enumerate(order)}
    for node in graph["nodes"]:
        net.add_node(
            _safe(node["id"]),
            label=_safe(node["id"]),
            title=_safe(
                f"{node['id']} | kampania: {node['campaign']} | rodzaje: {', '.join(node['kinds'])}"
            ),
            color=brand.singleton_color if node["singleton"] else color[node["campaign"]],
            shape="dot",
            size=14,
        )
    for link in graph["links"]:
        card = link["card"]
        tip = f"{link['score']:.2f} ({card['strength']}): {card['summary']} | " + " | ".join(
            card["reasons"][:4]
        )
        net.add_edge(
            _safe(link["a"]),
            _safe(link["b"]),
            value=link["score"],
            width=1 + 7 * link["score"],
            title=_safe(tip),
            color=brand.strong_edge_color if link["linked"] else brand.weak_edge_color,
            dashes=not link["linked"],
        )
    net.toggle_physics(True)
    return net.generate_html()
