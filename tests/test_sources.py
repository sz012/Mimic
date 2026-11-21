from app.sources import discover_items, kind_of


def test_discover_groups_files_per_directory(raw):
    items = {i.id: i for i in discover_items(raw)}
    assert set(items) == {"100", "200/strona_1", "300", "400"}
    assert items["200/strona_1"].case_id == "200"
    assert items["100"].paths["html"] == ["100/strona.html"]
    assert items["100"].paths["screenshot"] == ["100/zrzut.png"]
    assert sorted(items["400"].kinds) == ["meta", "video"]


def test_kind_of_handles_hidden_har(tmp_path):
    assert kind_of(tmp_path / ".har") == "har"
    assert kind_of(tmp_path / ".DS_Store") is None
    assert kind_of(tmp_path / "IMG_1.PNG") == "screenshot"
