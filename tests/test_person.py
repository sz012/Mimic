from engine.features.person import known_persons


def test_declined_names_match():
    hits = known_persons("Wywiad z Adamem Małyszem. Małysz powiedział, że Adam Małysz nie inwestuje.")
    assert hits.get("Adam Małysz", 0) >= 2


def test_names_without_spaces_from_ocr_match():
    assert "Adam Małysz" in known_persons("reklama adammalysz poleca")


def test_short_surname_requires_first_name():
    assert "Andrzej Duda" not in known_persons("dudek i dudy na łące")
    assert "Andrzej Duda" in known_persons("Andrzej Duda przemawia")
