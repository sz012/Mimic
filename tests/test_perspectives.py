from app.demo_items import demo_items
from engine.cluster import Workspace
from engine.cluster.perspectives import (
    DEFAULT_PERSPECTIVE,
    PERSPECTIVES,
    features_used,
    membership_table,
    perspective_weights,
    run_all,
    run_perspective,
)


def test_perspective_zeroes_other_groups():
    w = perspective_weights("operator")
    assert w.spec("infra.tracker_ids", "infra").weight > 0
    assert w.spec("text.narrative", "text").weight == 0
    assert w.spec("template.css_classes", "template").weight == 0
    assert not w.kit_as_campaign
    assert perspective_weights("platform").kit_as_campaign


def test_features_used_only_from_perspective_groups():
    rows = features_used("narrative")
    assert rows and all(name.startswith("text.") for name, _, _ in rows)
    assert [r[1] for r in rows] == sorted((r[1] for r in rows), reverse=True)


def test_default_perspective_matches_workspace(tmp_path):
    items = demo_items()
    ws = Workspace(items, tmp_path)
    res = run_perspective(items, DEFAULT_PERSPECTIVE, case_links=ws.case_links)
    assert res.label == {
        k: (None if ws.campaign(v).is_singleton else v) for k, v in ws.label.items()
    }


def test_all_perspectives_run_and_table_covers_items():
    items = demo_items()
    results = run_all(items)
    assert set(results) == set(PERSPECTIVES)
    rows = membership_table(results, items)
    assert len(rows) == len(items)
    assert all(len(r) == len(PERSPECTIVES) + 1 for r in rows)


def test_single_perspective_never_links_more_than_combined_on_demo():
    items = demo_items()
    results = run_all(items)
    combined = sum(len(c.items) for c in results["combined"].real)
    assert sum(len(c.items) for c in results["narrative"].real) <= combined
