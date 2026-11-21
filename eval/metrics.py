from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from sklearn.metrics import adjusted_rand_score


@dataclass
class PairReport:
    precision: float
    recall: float
    f1: float
    ari: float
    true_pairs: int
    predicted_pairs: int
    false_links: list[tuple[str, str]] = field(default_factory=list)
    missed_links: list[tuple[str, str]] = field(default_factory=list)


def _pairs(labels: dict[str, str]) -> set[tuple[str, str]]:
    return {(a, b) for a, b in combinations(sorted(labels), 2) if labels[a] == labels[b]}


def pair_report(truth: dict[str, str], predicted: dict[str, str]) -> PairReport:
    ids = sorted(set(truth) & set(predicted))
    t = {i: truth[i] for i in ids}
    p = {i: predicted[i] for i in ids}
    tp_set, pp_set = _pairs(t), _pairs(p)
    tp = len(tp_set & pp_set)
    precision = tp / len(pp_set) if pp_set else 1.0
    recall = tp / len(tp_set) if tp_set else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    ari = adjusted_rand_score([t[i] for i in ids], [p[i] for i in ids]) if len(ids) > 1 else 1.0
    return PairReport(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        ari=round(float(ari), 4),
        true_pairs=len(tp_set),
        predicted_pairs=len(pp_set),
        false_links=sorted(pp_set - tp_set),
        missed_links=sorted(tp_set - pp_set),
    )
