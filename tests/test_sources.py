from app import sources
from engine import ingest


def test_sources_delegate_to_ingest(raw, monkeypatch):
    monkeypatch.setenv("MIMIC_RAW_DIR", str(raw))
    assert sources.discover_items is ingest.discover_items
    assert sources.ingest_upload is ingest.ingest_upload
    items = {i.id: i for i in sources.load_items()}
    assert set(items) == {"100", "200/strona_1", "300", "400"}
    assert items["200/strona_1"].case_id == "200"
    assert sorted(items["400"].kinds) == ["meta", "video"]


def test_open_store_uses_db_path(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_DB_PATH", str(tmp_path / "m.sqlite"))
    store = sources.open_store()
    assert store.items() == []
