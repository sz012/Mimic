from engine.schema import Item
from eval.labels import load_truth
from eval.metrics import pair_report


def test_pair_report():
    truth = {"a": "1", "b": "1", "c": "2", "d": "2"}
    pred = {"a": "x", "b": "x", "c": "x", "d": "y"}
    rep = pair_report(truth, pred)
    assert rep.true_pairs == 2 and rep.predicted_pairs == 3
    assert rep.precision == round(1 / 3, 4)
    assert rep.recall == 0.5
    assert ("a", "c") in rep.false_links
    assert ("c", "d") in rep.missed_links


def test_perfect_clustering():
    truth = {"a": "1", "b": "1", "c": "2"}
    rep = pair_report(truth, {"a": "k", "b": "k", "c": "m"})
    assert rep.precision == rep.recall == rep.ari == 1.0


def test_case_labels_expand_to_items(tmp_path):
    f = tmp_path / "labels.csv"
    f.write_text("case_id,campaign\n61,K1\n1,K2\n", encoding="utf-8")
    items = [Item("61/strona_1", "61"), Item("61/strona_2", "61"), Item("1", "1"), Item("9", "9")]
    assert load_truth(items, [f]) == {"61/strona_1": "K1", "61/strona_2": "K1", "1": "K2"}
