from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import imagehash

from engine.similarity.context import Context

PHASH_MATCH = 8
SCREEN_MATCH = 12
MAX_SHOWN = 8


@dataclass
class Result:
    score: float
    note: str
    left: Any
    right: Any


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _short(values: list, n: int = MAX_SHOWN) -> list:
    return values[:n] + ([f"... (+{len(values) - n})"] if len(values) > n else [])


def _split_common(name: str, values: set[str], ctx: Context | None) -> tuple[set[str], set[str]]:
    if ctx is None:
        return values, set()
    common = {v for v in values if ctx.is_common(name, v)}
    return values - common, common


def set_overlap(name: str, a: list, b: list, ctx: Context | None) -> Result:
    sa, ca = _split_common(name, set(a), ctx)
    sb, cb = _split_common(name, set(b), ctx)
    shared = sorted(sa & sb)
    union = sa | sb
    if not union:
        return Result(
            0.0,
            "tylko wartości pospolite w zbiorze (zignorowane)",
            _short(sorted(a)),
            _short(sorted(b)),
        )
    jac = len(shared) / len(union)
    containment = len(shared) / max(1, min(len(sa), len(sb)))
    score = _clamp(0.5 * jac + 0.5 * containment)
    note = f"wspólne: {', '.join(_short(shared, 6)) or 'brak'} (Jaccard {jac:.2f}, pokrycie {containment:.2f})"
    ignored = (ca | cb) & set(a) & set(b)
    if ignored:
        note += f"; pominięto {len(ignored)} pospolitych"
    return Result(score, note, _short(shared or sorted(a)), _short(shared or sorted(b)))


def shared_values(name: str, a: list, b: list, ctx: Context | None) -> Result:
    sa, _ = _split_common(name, set(a), ctx)
    sb, _ = _split_common(name, set(b), ctx)
    shared = sorted(sa & sb)
    score = 1.0 if shared else 0.0
    note = (
        f"ta sama wartość: {', '.join(_short(shared, 5))}" if shared else "brak wspólnych wartości"
    )
    return Result(score, note, _short(shared or sorted(a)), _short(shared or sorted(b)))


def minhash(name: str, a: dict, b: dict, ctx: Context | None) -> Result:
    ha, hb = a.get("minhash", []), b.get("minhash", [])
    if not ha or len(ha) != len(hb):
        return Result(0.0, "niezgodne sygnatury", None, None)
    jac = sum(1 for x, y in zip(ha, hb) if x == y) / len(ha)
    score = _clamp((jac - 0.1) / 0.5)
    unit = "5-gramach znaków" if name == "text.ocr" else "3-gramach słów"
    note = f"podobieństwo tekstu (MinHash Jaccard {jac:.2f} na {unit})"
    return Result(score, note, a.get("preview", ""), b.get("preview", ""))


def _hamming(x: str, y: str) -> int:
    return int(imagehash.hex_to_hash(x) - imagehash.hex_to_hash(y))


def image_set(name: str, a: list, b: list, ctx: Context | None) -> Result:
    pa = [e for e in a if not (ctx and ctx.is_common(name, e["phash"]))]
    pb = [e for e in b if not (ctx and ctx.is_common(name, e["phash"]))]
    matches = []
    used = set()
    for ea in pa:
        best = None
        for j, eb in enumerate(pb):
            if j in used:
                continue
            d = _hamming(ea["phash"], eb["phash"])
            if d <= PHASH_MATCH and (best is None or d < best[0]):
                best = (d, j, eb)
        if best:
            used.add(best[1])
            matches.append((best[0], ea["src"], best[2]["src"]))
    k = len(matches)
    score = 1 - 0.6**k if k else 0.0
    note = (
        f"{k} wspólnych obrazów (pHash, odległość ≤ {PHASH_MATCH})"
        if k
        else "brak wspólnych obrazów"
    )
    return Result(score, note, _short([m[1] for m in matches]), _short([m[2] for m in matches]))


def screenshot(
    name: str, a: list, b: list, ctx: Context | None, a_extra: list = (), b_extra: list = ()
) -> Result:
    best = None
    for ea in a:
        for eb in list(b) + list(b_extra):
            for key in ("phash", "top_phash"):
                if key in ea and key in eb:
                    d = _hamming(ea[key], eb[key])
                    if best is None or d < best[0]:
                        best = (d, ea["src"], eb["src"], key)
            if "phash" in eb:
                d = _hamming(ea.get("top_phash", ea["phash"]), eb["phash"])
                if best is None or d < best[0]:
                    best = (d, ea["src"], eb["src"], "top_phash")
    for eb in b:
        for ea in a_extra:
            d = _hamming(ea["phash"], eb.get("top_phash", eb["phash"]))
            if best is None or d < best[0]:
                best = (d, ea["src"], eb["src"], "phash")
    if best is None:
        return Result(0.0, "brak porównywalnych obrazów", None, None)
    d = best[0]
    score = _clamp(1 - d / (SCREEN_MATCH + 4)) if d <= SCREEN_MATCH else 0.0
    return Result(score, f"najbliższy zrzut/obraz: odległość pHash {d}", best[1], best[2])


def same_label(name: str, a: list, b: list, ctx: Context | None) -> Result:
    la, lb = (a or [None])[0], (b or [None])[0]
    return Result(1.0 if la == lb else 0.0, f"temat: {la} / {lb}", la, lb)


def cosine(name: str, a: list, b: list, ctx: Context | None) -> Result:
    num = sum(x * y for x, y in zip(a, b))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    sim = num / den if den else 0.0
    return Result(_clamp((sim - 0.5) / 0.4), f"podobieństwo kosinusowe {sim:.2f}", None, None)


def face_vectors(name: str, a: list, b: list, ctx: Context | None) -> Result:
    from engine.features.faces import threshold

    limit = threshold()
    best = -1.0
    for x in a:
        for y in b:
            den = math.sqrt(sum(p * p for p in x)) * math.sqrt(sum(q * q for q in y))
            if den:
                best = max(best, sum(p * q for p, q in zip(x, y)) / den)
    left, right = f"{len(a)} twarzy", f"{len(b)} twarzy"
    if best < limit:
        return Result(
            0.0, f"brak wspólnej twarzy (najbliższe podobieństwo {best:.2f})", left, right
        )
    score = 0.5 + 0.5 * _clamp((best - limit) / max(0.01, 0.7 - limit))
    return Result(score, f"ta sama twarz na obu materiałach (podobieństwo {best:.2f})", left, right)


def hash_distance(name: str, a: str, b: str, ctx: Context | None) -> Result:
    try:
        d = _hamming(a, b)
    except ValueError:
        same = a == b
        return Result(
            1.0 if same else 0.0, "identyczna wartość" if same else "różne wartości", a, b
        )
    bits = len(a) * 4
    return Result(_clamp(1 - d / (bits * 0.25)), f"odległość Hamminga {d}/{bits}", a, b)


def date_proximity(name: str, a: Any, b: Any, ctx: Context | None) -> Result:
    def parse(v: Any) -> date | None:
        v = v[0] if isinstance(v, list) and v else v
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return None

    da, db = parse(a), parse(b)
    if da is None or db is None:
        return Result(0.0, "nieczytelna data", a, b)
    days = abs((da - db).days)
    score = 1.0 if days <= 3 else _clamp(1 - (days - 3) / 27)
    return Result(score, f"daty rejestracji różnią się o {days} dni", str(da), str(db))


def exact(name: str, a: Any, b: Any, ctx: Context | None) -> Result:
    if isinstance(a, str) and ctx and ctx.is_common(name, a):
        return Result(0.0, f"wartość pospolita: {a}", a, b)
    same = a == b
    return Result(
        1.0 if same else 0.0, f"identyczna wartość: {a}" if same else "różne wartości", a, b
    )


def generic(name: str, a: Any, b: Any, ctx: Context | None) -> Result:
    if isinstance(a, list) and isinstance(b, list):
        if a and isinstance(a[0], (int, float)) and b and isinstance(b[0], (int, float)):
            return cosine(name, a, b, ctx)
        if (a and isinstance(a[0], dict) and "phash" in a[0]) or (
            b and isinstance(b[0], dict) and "phash" in b[0]
        ):
            return image_set(name, a, b, ctx)
        return set_overlap(name, [str(x) for x in a], [str(x) for x in b], ctx)
    if isinstance(a, dict) and "minhash" in a:
        return minhash(name, a, b, ctx)
    if isinstance(a, str) and isinstance(b, str) and len(a) == len(b) and len(a) in (16, 32, 64):
        return hash_distance(name, a, b, ctx)
    return exact(name, a, b, ctx)


Comparator = Callable[..., Result]
