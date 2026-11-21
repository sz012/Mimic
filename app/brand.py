from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BRAND_FILE = Path(__file__).parent / "assets" / "brand.json"

DEFAULT_PALETTE = [
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
DEFAULT_GROUP_COLORS = {
    "text": "#1f77b4",
    "visual": "#2ca02c",
    "person": "#9467bd",
    "infra": "#d62728",
    "template": "#ff7f0e",
}


@dataclass
class Brand:
    campaign_palette: list[str] = field(default_factory=lambda: list(DEFAULT_PALETTE))
    group_colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GROUP_COLORS))
    singleton_color: str = "#9e9e9e"
    weak_edge_color: str = "#cccccc"
    strong_edge_color: str = "#333333"

    def campaign_color(self, index: int) -> str:
        return self.campaign_palette[index % len(self.campaign_palette)]


def load_brand(path: Path = BRAND_FILE) -> Brand:
    brand = Brand()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return brand
    if not isinstance(data, dict):
        return brand
    palette = data.get("campaign_palette")
    if isinstance(palette, list) and palette and all(isinstance(c, str) for c in palette):
        brand.campaign_palette = palette
    groups = data.get("group_colors")
    if isinstance(groups, dict):
        brand.group_colors.update({k: v for k, v in groups.items() if isinstance(v, str)})
    for key in ("singleton_color", "weak_edge_color", "strong_edge_color"):
        if isinstance(data.get(key), str):
            setattr(brand, key, data[key])
    return brand
