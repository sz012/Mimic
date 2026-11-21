from pathlib import Path

from engine.schema import Assignment, Campaign, Evidence, Feature, Item
from engine.store import Store, load_items


def sample_item(item_id: str = "1") -> Item:
    return Item(
        id=item_id,
        case_id="1",
        paths={"html": ["1/a.html"], "assets": ["1/a_files"]},
        features={
            "text.title": Feature("text.title", "text", ["tytul"], 0.9, "html:1/a.html"),
            "infra.created": Feature.missing("infra.created", "infra", "offline"),
        },
    )


def test_item_roundtrip_with_features(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    item = sample_item()
    store.upsert_item(item)
    loaded = store.get_item("1")
    assert loaded == item
    assert loaded.features["infra.created"].available is False


def test_upsert_replaces_and_items_sorted(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.upsert_item(sample_item("2"))
    store.upsert_item(sample_item("1"))
    changed = sample_item("1")
    changed.paths["html"] = ["1/b.html"]
    store.upsert_item(changed)
    items = store.items()
    assert [i.id for i in items] == ["1", "2"]
    assert items[0].paths["html"] == ["1/b.html"]
    assert store.get_item("brak") is None


def test_campaigns_and_assignments_roundtrip(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.save_campaigns([Campaign("K01", ["1", "2"]), Campaign("N02", ["3"])])
    store.save_campaigns([Campaign("K01", ["1", "2", "4"])])
    assert store.campaigns() == [Campaign("K01", ["1", "2", "4"])]
    ev = Evidence("infra.tracker_ids", "infra", 0.95, 1.0, ["fbpixel:1"], ["fbpixel:1"], "ten sam")
    store.save_assignment(Assignment("5", "K01", 0.97, [ev]))
    store.save_assignment(Assignment("6", None, 0.1, []))
    got = {a.item_id: a for a in store.assignments()}
    assert got["5"].evidence == [ev]
    assert got["6"].is_new_pattern


def test_clear_empties_everything(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.upsert_item(sample_item())
    store.save_campaigns([Campaign("K01", ["1"])])
    store.save_assignment(Assignment("1", "K01", 0.9, []))
    store.clear()
    assert store.items() == [] and store.campaigns() == [] and store.assignments() == []


def test_load_items_empty_without_db_and_reads_env_path(tmp_path, monkeypatch):
    db = tmp_path / "x" / "db.sqlite"
    monkeypatch.setenv("MIMIC_DB_PATH", str(db))
    assert load_items() == []
    assert not db.exists()
    Store().upsert_item(sample_item())
    assert [i.id for i in load_items()] == ["1"]


def test_store_creates_parent_directory(tmp_path):
    path = tmp_path / "a" / "b" / "db.sqlite"
    Store(path)
    assert Path(path).exists()
