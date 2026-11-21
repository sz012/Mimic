import json
from pathlib import Path

import pytest

from engine.ingest import discover_items
from engine.schema import Item
from scripts.labels_check import campaigns, check


def items() -> list[Item]:
    return [
        Item("1", "1"),
        Item("61", "61"),
        Item("61/strona_1", "61"),
        Item("61/strona_2", "61"),
        Item("5", "5"),
    ]


def test_case_label_is_inherited_by_all_items_of_the_case():
    labels = {"1": "A", "61": "B", "5": "C"}
    unknown, unlabeled = check(labels, items())
    assert unknown == [] and unlabeled == []
    assert campaigns(labels, items())["B"] == ["61", "61/strona_1", "61/strona_2"]


def test_item_label_overrides_case_label():
    labels = {"1": "A", "61": "B", "61/strona_2": "X", "5": "C"}
    assert campaigns(labels, items())["X"] == ["61/strona_2"]
    assert campaigns(labels, items())["B"] == ["61", "61/strona_1"]


def test_unknown_and_unlabeled_are_reported():
    unknown, unlabeled = check({"1": "A", "99": "Z"}, items())
    assert unknown == ["99"]
    assert unlabeled == ["5", "61", "61/strona_1", "61/strona_2"]


def test_committed_labels_match_real_data_when_present():
    raw = Path("data/raw")
    labels_file = Path("data/labels/labels.json")
    if not raw.is_dir() or not labels_file.exists():
        pytest.skip("brak danych organizatora")
    labels = json.loads(labels_file.read_text(encoding="utf-8"))
    unknown, unlabeled = check(labels, discover_items(raw))
    assert unknown == [] and unlabeled == []
    assert all(isinstance(v, str) and v for v in labels.values())
