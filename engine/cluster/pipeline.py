from __future__ import annotations

import hashlib
import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from itertools import combinations
from pathlib import Path

from engine.schema import Edge, Feature, Item
from engine.similarity import Context, Weights, build_context, compare
from engine.similarity.candidates import candidate_pairs
from engine.similarity.weights import DEFAULT

EXTRACTORS = (
    "engine.features.text",
    "engine.features.visual",
    "engine.features.person",
    "engine.features.infra",
    "engine.features.template",
)
CACHE_VERSION = "4"
FULL_PAIRS_LIMIT = 40
WORKERS = 4
EXTRACT_ERRORS = (
    OSError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
    IndexError,
    RuntimeError,
    MemoryError,
)


def _extractors() -> list[tuple[str, str, object]]:
    out = []
    for mod_name in EXTRACTORS:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        fn = getattr(mod, "extract", None)
        if callable(fn):
            out.append((mod_name, str(getattr(mod, "VERSION", "0")), fn))
    return out


def _fingerprint(item: Item, raw_dir: Path, versions: list[str]) -> str:
    h = hashlib.sha1(CACHE_VERSION.encode())
    h.update(",".join(versions).encode())
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


def has_features(item: Item) -> bool:
    return any(f.available and f.value not in (None, [], {}) for f in item.features.values())


def extract_features(item: Item, raw_dir: Path, cache_dir: Path | None = None) -> Item:
    raw_dir = Path(raw_dir)
    extractors = _extractors()
    fp = _fingerprint(item, raw_dir, [f"{n}:{v}" for n, v, _ in extractors])
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
    for mod_name, _, fn in extractors:
        try:
            computed.update(fn(item, raw_dir))
        except EXTRACT_ERRORS as exc:
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


def extract_all(
    items: list[Item], raw_dir: Path, cache_dir: Path | None = None, workers: int = WORKERS
) -> list[Item]:
    if workers <= 1 or len(items) <= 1:
        return [extract_features(i, raw_dir, cache_dir) for i in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda i: extract_features(i, raw_dir, cache_dir), items))


def all_edges(
    items: list[Item],
    context: Context | None = None,
    weights: Weights = DEFAULT,
    min_score: float = 0.0,
    full_pairs_limit: int = FULL_PAIRS_LIMIT,
) -> list[Edge]:
    ctx = context or build_context(items)
    if len(items) <= full_pairs_limit:
        pairs = combinations(range(len(items)), 2)
    else:
        pairs = sorted(candidate_pairs(items, ctx, weights))
    edges = []
    for i, j in pairs:
        e = compare(items[i], items[j], ctx, weights, min_score)
        if e is not None:
            edges.append(e)
    return edges
