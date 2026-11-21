from engine.features.person import known_persons


def test_declined_names_match():
    hits = known_persons(
        "Wywiad z Rafałem Brzoską. Brzoska powiedział, że Rafał Brzoska nie inwestuje."
    )
    assert hits.get("Rafał Brzoska", 0) >= 2


def test_short_surname_requires_first_name():
    assert "Tomasz Lis" not in known_persons("lista zakupów i listopad")
    assert "Tomasz Lis" in known_persons("Tomasz Lis prowadzi program")
