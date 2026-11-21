import copy

import engine.features.text as text_module
from app.sources import discover_items
from engine.cluster import cluster, labels_of
from engine.cluster.campaigns import assign_detail
from engine.cluster.pipeline import all_edges, extract_all, extract_features
from engine.explain import edge_card
from engine.schema import Feature, Item
from engine.similarity import build_context, compare
from eval.holdout import holdout
from eval.run_eval import duplicate_check
from eval.synthetic import synthetic_corpus
from eval.variants import variants_report


def test_candidate_index_matches_full_comparison():
    items, _ = synthetic_corpus(campaigns=10, per_campaign=5, singles=10)
    assert len(items) > 40
    ctx = build_context(items)
    full = labels_of(cluster(items, all_edges(items, ctx, full_pairs_limit=10_000)))
    fast = labels_of(cluster(items, all_edges(items, ctx, full_pairs_limit=0)))
    assert full == fast


def test_item_without_features_is_insufficient_not_duplicate():
    empty = Item(
        "pusty",
        "pusty",
        {"har": ["pusty/.har"]},
        {"text.title": Feature.missing("text.title", "text", "brak")},
    )
    items, _ = synthetic_corpus(campaigns=2, per_campaign=2, singles=0)
    detail = assign_detail(empty, cluster(items, all_edges(items)))
    assert detail.status == "za_malo_danych" and detail.assignment.campaign_id is None
    report = duplicate_check([empty, *items])
    assert report["insufficient"] == ["pusty"]
    assert report["rate"] == 1.0


def test_holdout_and_variants_on_synthetic():
    items, truth = synthetic_corpus()
    h = holdout(items, truth).summary()
    assert h["false_assignments"] == 0
    assert h["assign_precision"] == 1.0
    assert h["new_pattern_recall"] == 1.0
    v = variants_report(items)
    assert v["duplikat"]["odpornosc"] == 1.0
    assert all(r["falszywe"] == 0 for r in v.values())


def test_counterfactual_explains_both_directions():
    items, _ = synthetic_corpus(campaigns=2, per_campaign=4, singles=1)
    edges = sorted(all_edges(items), key=lambda e: -e.score)
    linked = edge_card(edges[0])
    assert linked["linked"] and linked["counterfactual"].startswith("Rozdzieliłoby")
    weak = edge_card(edges[-1])
    assert not weak["linked"] and weak["counterfactual"]


def test_module_version_invalidates_cache(raw, tmp_path, monkeypatch):
    item = discover_items(raw)[0]
    first = extract_features(copy.deepcopy(item), raw, tmp_path)
    monkeypatch.setattr(text_module, "VERSION", "zmieniona")
    calls = []
    original = text_module.extract
    monkeypatch.setattr(text_module, "extract", lambda i, r: calls.append(i.id) or original(i, r))
    second = extract_features(copy.deepcopy(item), raw, tmp_path)
    assert calls == [item.id]
    assert set(first.features) == set(second.features)


def test_parallel_extraction_equals_sequential(raw, tmp_path):
    seq = extract_all(discover_items(raw), raw, None, workers=1)
    par = extract_all(discover_items(raw), raw, None, workers=4)
    assert [i.id for i in seq] == [i.id for i in par]
    for a, b in zip(seq, par):
        assert {k: v.value for k, v in a.features.items()} == {
            k: v.value for k, v in b.features.items()
        }
    assert compare(seq[0], par[0]).score > 0.9
