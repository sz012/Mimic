from dataclasses import dataclass, field
from typing import Any, Literal

Group = Literal["text", "visual", "infra", "template", "person"]
Kind = Literal["html", "har", "screenshot", "video", "meta", "url"]


@dataclass(frozen=True)
class Feature:
    name: str
    group: Group
    value: Any = None
    confidence: float = 0.0
    source: str = ""
    available: bool = True

    @classmethod
    def missing(cls, name: str, group: Group, source: str = "") -> "Feature":
        return cls(name=name, group=group, value=None, confidence=0.0, source=source, available=False)


@dataclass
class Item:
    id: str
    case_id: str
    paths: dict[Kind, list[str]] = field(default_factory=dict)
    features: dict[str, Feature] = field(default_factory=dict)

    @property
    def kinds(self) -> list[Kind]:
        return [k for k, v in self.paths.items() if v]


@dataclass(frozen=True)
class Evidence:
    feature: str
    group: Group
    weight: float
    score: float
    left: Any = None
    right: Any = None
    note: str = ""


@dataclass
class Edge:
    a: str
    b: str
    score: float
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Campaign:
    id: str
    members: list[str] = field(default_factory=list)


@dataclass
class Assignment:
    item_id: str
    campaign_id: str | None
    score: float
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def is_new_pattern(self) -> bool:
        return self.campaign_id is None
