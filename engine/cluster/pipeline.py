from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import asdict
from itertools import combinations
from pathlib import Path

from engine.schema import Edge, Feature, Item
from engine.similarity import Context, Weights, build_context, compare
from engine.similarity.weights import DEFAULT

EXTRACTORS = (
    "engine.features.text",
    "engine.features.visual",
    "engine.features.person",
    "engine.features.infra",
    "engine.features.template",
)
CACHE_VERSION = "3"


def _extractors():
    out = []
    for mod_name in EXTRACTORS:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        fn = getattr(mod, "extract", None)
        if callable(fn):
            out.append((mod_name, fn))
    return out


def _fingerprint(item: Item, raw_dir: Path, names: list[str]) -> str:
    h = hashlib.sha1(CACHE_VERSION.encode())
    h.update(",".join(names).encode())
    for kind in sorted(item.paths):
        for rel in item.paths[kind]:
            p = raw_dir / rel
            try:
                st = p.stat()
                h.update(f"{rel}:{st.st_size}:{int(st.st_mtime)}".encode())
            except OSError:
                h.update(f"{rel}:missing".encode())
    return h.hexdigest()


def _cache_path(cache_dir: Path, item: Item) -> Path:
    safe = hashlib.sha1(item.id.encode()).hexdigest()[:16]
    return cache_dir / "features" / f"{safe}.json"


def extract_features(item: Item, raw_dir: Path, cache_dir: Path | None = None) -> Item:
    raw_dir = Path(raw_dir)
    extractors = _extractors()
    fp = _fingerprint(item, raw_dir, [n for n, _ in extractors])
    cache_file = _cache_path(Path(cache_dir), item) if cache_dir else None
    if cache_file and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if data.get("fingerprint") == fp:
                for name, f in data["features"].items():
                    item.features.setdefault(name, Feature(**f))
                return item
        except (ValueError, TypeError, KeyError):
            pass
    computed: dict[str, Feature] = {}
    for mod_name, fn in extractors:
        try:
            computed.update(fn(item, raw_dir))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            IndexError,
            RuntimeError,
        ) as exc:
            group = mod_name.rsplit(".", 1)[-1]
            computed[f"{group}.error"] = Feature.missing(
                f"{group}.error", group, f"błąd ekstrakcji: {exc!r}"
            )
    for name, f in computed.items():
        item.features.setdefault(name, f)
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fingerprint": fp,
            "item": item.id,
            "features": {k: asdict(v) for k, v in computed.items()},
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False))
    return item


def all_edges(
    items: list[Item],
    context: Context | None = None,
    weights: Weights = DEFAULT,
    min_score: float = 0.0,
) -> list[Edge]:
    ctx = context or build_context(items)
    edges = []
    for a, b in combinations(items, 2):
        e = compare(a, b, ctx, weights, min_score)
        if e is not None:
            edges.append(e)
    return edges
