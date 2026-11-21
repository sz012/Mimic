from __future__ import annotations

import random
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

STORY = (
    "Znany ekspert ujawnia sekretną platformę inwestycyjną, która pozwala zarabiać codziennie. "
    "Wystarczy rejestracja i niewielka wpłata, a algorytm sam pomnaża kapitał bez ryzyka dla klienta. "
    "Tysiące osób już skorzystały, a banki próbują ukryć tę metodę przed zwykłymi ludźmi w całym kraju."
)
OTHER_STORY = (
    "Nowy suplement na stawy łagodzi ból już po tygodniu stosowania według opinii pacjentów z wielu miast. "
    "Kapsułki zawierają naturalne składniki, a promocja obowiązuje tylko dziś przy zamówieniu przez formularz. "
    "Lekarze polecają kurację osobom starszym, które szukają prostego sposobu na poprawę codziennej sprawności."
)


def page(title: str, story: str, extra: str = "") -> str:
    paras = "".join(f"<p>{s.strip()}.</p>" for s in story.split(".") if s.strip())
    return f"<html><head><title>{title}</title><script>var x=1;</script></head><body><h1>{title}</h1>{paras}{extra}</body></html>"


def picture(seed: int, size: tuple[int, int] = (200, 160)) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    draw = ImageDraw.Draw(img)
    for _ in range(12):
        x0, y0 = rnd.randrange(size[0]), rnd.randrange(size[1])
        draw.rectangle(
            [x0, y0, x0 + rnd.randrange(20, 80), y0 + rnd.randrange(20, 80)],
            fill=(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)),
        )
    return img


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    a = root / "100"
    a.mkdir(parents=True)
    (a / "strona.html").write_text(
        page(
            "Sekret bankiera Jan Testowy",
            STORY,
            '<a href="tel:+48 501 502 503">zadzwoń</a> kontakt@przyklad.test',
        ),
        encoding="utf-8",
    )
    assets = a / "strona_files"
    assets.mkdir()
    picture(1).save(assets / "foto.png")
    picture(2).save(assets / "baner.jpg")
    picture(3, (40, 40)).save(assets / "ikona.png")
    picture(7, (390, 840)).save(a / "zrzut.png")
    b = root / "200" / "strona_1"
    b.mkdir(parents=True)
    (b / "inna.html").write_text(
        page("Sekret bankiera ujawniony", STORY, "<p>Dzwoń 501-502-503</p>"), encoding="utf-8"
    )
    b_assets = b / "inna_files"
    b_assets.mkdir()
    picture(1).save(b_assets / "kopia.png")
    c = root / "300"
    c.mkdir()
    (c / "suplement.html").write_text(page("Kapsułki na stawy", OTHER_STORY), encoding="utf-8")
    d = root / "400"
    d.mkdir()
    (d / "film.info.json").write_text(
        '{"title": "Reklama testowa", "description": "Opis filmu reklamowego"}', encoding="utf-8"
    )
    (d / "film.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    (root / "200" / ".DS_Store").write_bytes(b"x")
    return root
