from __future__ import annotations

import json
from html import escape
from typing import Any

from pyvis.network import Network

from app.brand import Brand


def _safe(text: str) -> str:
    return escape(text).replace("\n", " ")


OPTIONS = {
    "physics": {
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
            "gravitationalConstant": -60,
            "springLength": 120,
            "avoidOverlap": 0.5,
        },
        "stabilization": {"enabled": True, "iterations": 400, "fit": True},
    },
    "edges": {"smooth": False},
    "nodes": {"font": {"size": 14}},
    "interaction": {"hover": True, "tooltipDelay": 100},
}
FIT_SCRIPT = (
    "<script>function mimicFit() { network.redraw(); network.fit({animation: false}); }"
    "network.on('stabilized', function () { network.setOptions({physics: false}); mimicFit(); });"
    "new ResizeObserver(mimicFit).observe(document.getElementById('mynetwork'));"
    "setTimeout(mimicFit, 800); setTimeout(mimicFit, 2500);</script>"
)


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
        if link.get("case"):
            net.add_edge(
                _safe(link["a"]),
                _safe(link["b"]),
                width=2,
                title=_safe(tip),
                color=brand.case_edge_color,
                dashes=[2, 6],
            )
            continue
        net.add_edge(
            _safe(link["a"]),
            _safe(link["b"]),
            width=1 + 5 * link["score"],
            title=_safe(tip),
            color=brand.strong_edge_color if link["linked"] else brand.weak_edge_color,
            dashes=not link["linked"],
        )
    net.set_options(json.dumps(OPTIONS))
    return net.generate_html().replace("</body>", FIT_SCRIPT + "</body>", 1)
