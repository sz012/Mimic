from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from engine.cluster.campaigns import Campaign, Method, assign_detail, cluster
from engine.cluster.pipeline import all_edges, has_features
from engine.schema import Item
from engine.similarity import Weights, build_context
from engine.similarity.rules import LINK_THRESHOLD
from engine.similarity.weights import DEFAULT


@dataclass
class HoldoutReport:
    evaluated: int = 0
    correct: int = 0
    assigned: int = 0
    assigned_correct: int = 0
    expected_new: int = 0
    new_correct: int = 0
    expected_known: int = 0
    known_correct: int = 0
    false_assignments: list[tuple[str, str, str]] = field(default_factory=list)
    missed: list[tuple[str, str]] = field(default_factory=list)
    insufficient: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        def ratio(a: int, b: int) -> float:
            return round(a / b, 4) if b else 1.0

        return {
            "evaluated": self.evaluated,
            "accuracy": ratio(self.correct, self.evaluated),
            "assign_precision": ratio(self.assigned_correct, self.assigned),
            "known_recall": ratio(self.known_correct, self.expected_known),
            "new_pattern_recall": ratio(self.new_correct, self.expected_new),
            "false_assignments": len(self.false_assignments),
            "insufficient": len(self.insufficient),
        }


def _majority(campaign: Campaign, truth: dict[str, str]) -> str | None:
    labels = Counter(truth[i.id] for i in campaign.items if i.id in truth)
    return labels.most_common(1)[0][0] if labels else None


def holdout(
    items: list[Item],
    truth: dict[str, str],
    threshold: float = LINK_THRESHOLD,
    method: Method = "components",
    weights: Weights = DEFAULT,
    case_links: bool = False,
) -> HoldoutReport:
    report = HoldoutReport()
    cases = sorted({i.case_id for i in items if i.id in truth})
    for case in cases:
        held = [i for i in items if i.case_id == case and i.id in truth]
        rest = [i for i in items if i.case_id != case]
        ctx = build_context(rest)
        campaigns = cluster(
            rest, all_edges(rest, ctx, weights), threshold, method, case_links, weights
        )
        rest_labels = {truth[i.id] for i in rest if i.id in truth}
        for item in held:
            if not has_features(item):
                report.insufficient.append(item.id)
                continue
            report.evaluated += 1
            label = truth[item.id]
            detail = assign_detail(item, campaigns, ctx, weights, threshold)
            chosen = next((c for c in campaigns if c.id == detail.assignment.campaign_id), None)
            expected_known = label in rest_labels
            if expected_known:
                report.expected_known += 1
            else:
                report.expected_new += 1
            if chosen is None:
                if expected_known:
                    report.missed.append((item.id, label))
                else:
                    report.correct += 1
                    report.new_correct += 1
                continue
            report.assigned += 1
            got = _majority(chosen, truth)
            if expected_known and got == label:
                report.correct += 1
                report.assigned_correct += 1
                report.known_correct += 1
            else:
                report.false_assignments.append((item.id, label, f"{chosen.id}:{got}"))
    return report
