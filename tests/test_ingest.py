import io
import zipfile
from email.message import EmailMessage
from pathlib import Path

import pytest

from engine.ingest import discover_items, fetch, ingest_upload
from engine.ingest.kinds import kind_of
from engine.ingest.mhtml import convert_mhtml, safe_name


def write(path: Path, content: bytes | str = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return path


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    write(root / "1" / "strona.html")
    write(root / "1" / "strona_files" / "a.png")
    write(root / "1" / "domena.test.har")
    write(root / "1" / "zrzut.PNG")
    write(root / "1" / "nagranie.MP4")
    write(root / "1" / "plik.pobrane")
    write(root / "61" / "reklama.png")
    write(root / "61" / "strona_1" / ".har")
    write(root / "61" / "strona_1" / "tytul_files" / "b.jpg")
    write(root / "61" / "strona_2" / "x.har")
    write(root / "14" / "zapis" / "zapis" / "dom.html")
    write(root / "14" / "zapis" / "zapis" / "page.mhtml")
    write(root / "14" / "zapis" / "zapis" / "page.har")
    write(root / "14" / "zapis" / "zapis" / "manifest.json")
    write(root / "14" / "zapis" / "zapis" / "resources" / "script" / "s.js")
    write(root / "5" / "info.json")
    write(root / "5" / "film.mp4")
    write(root / "9" / "tylko.mhtml")
    write(root / ".ukryty" / "x.html")
    write(root / "__MACOSX" / "x.html")
    return root


def test_kind_of_rules():
    assert kind_of(Path(".har")) == "har"
    assert kind_of(Path("x.HAR")) == "har"
    assert kind_of(Path("a.mht")) == "html"
    assert kind_of(Path("a.webp")) == "screenshot"
    assert kind_of(Path("a.MKV")) == "video"
    assert kind_of(Path("a.pobrane")) is None
    assert kind_of(Path(".DS_Store")) is None
    assert kind_of(Path("._x.png")) is None


def test_discover_ids_and_case_ids(tree):
    items = {i.id: i for i in discover_items(tree)}
    assert set(items) == {
        "1",
        "61",
        "61/strona_1",
        "61/strona_2",
        "14/zapis/zapis",
        "5",
        "9",
    }
    assert items["61/strona_1"].case_id == "61"
    assert items["14/zapis/zapis"].case_id == "14"


def test_discover_paths_and_assets(tree):
    items = {i.id: i for i in discover_items(tree)}
    one = items["1"].paths
    assert one["html"] == ["1/strona.html"]
    assert one["har"] == ["1/domena.test.har"]
    assert one["screenshot"] == ["1/zrzut.PNG"]
    assert one["video"] == ["1/nagranie.MP4"]
    assert one["assets"] == ["1/strona_files"]
    assert "plik.pobrane" not in str(one)
    assert items["61/strona_1"].paths == {
        "har": ["61/strona_1/.har"],
        "assets": ["61/strona_1/tytul_files"],
    }
    assert items["61"].paths == {"screenshot": ["61/reklama.png"]}


def test_page_capture_prefers_plain_html_and_collects_resources(tree):
    item = {i.id: i for i in discover_items(tree)}["14/zapis/zapis"]
    assert item.paths["html"] == ["14/zapis/zapis/dom.html"]
    assert item.paths["meta"] == ["14/zapis/zapis/manifest.json"]
    assert item.paths["assets"] == ["14/zapis/zapis/resources"]


def test_mhtml_alone_is_html_kind(tree):
    item = {i.id: i for i in discover_items(tree)}["9"]
    assert item.paths == {"html": ["9/tylko.mhtml"]}


def test_discover_is_deterministic_and_handles_missing_root(tree, tmp_path):
    first = [(i.id, i.paths) for i in discover_items(tree)]
    assert first == [(i.id, i.paths) for i in discover_items(tree)]
    assert discover_items(tmp_path / "brak") == []


def test_discover_ignores_hidden_and_macosx(tree):
    ids = {i.id for i in discover_items(tree)}
    assert not any(x.startswith((".", "__MACOSX")) for x in ids)


def build_mhtml(html: str) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "zapis"
    msg.set_content("")
    msg.make_mixed()
    related = EmailMessage()
    related.set_content(html, subtype="html")
    related.add_related(
        b"\x89PNGdata",
        "image",
        "png",
        cid="<a>",
        headers=["Content-Location: https://x.test/img/logo.png"],
    )
    msg.attach(related)
    return msg.as_bytes()


def test_convert_mhtml_extracts_html_and_assets(tmp_path):
    source = write(tmp_path / "strona.mhtml", build_mhtml("<html><body>Witaj</body></html>"))
    html = convert_mhtml(source, tmp_path)
    assert html is not None and html.suffix == ".html"
    assert "Witaj" in html.read_text()
    assert (tmp_path / f"{html.stem}_files" / "logo.png").exists()


def test_safe_name_blocks_traversal():
    assert safe_name("../../etc/passwd") == "passwd"
    assert safe_name("a/b\\c.html") == "c.html"
    assert safe_name("") == "plik"
    assert safe_name(".har") == ".har"
    assert safe_name("..") == "plik"


def make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_ingest_upload_files_and_url(tmp_path):
    item = ingest_upload(
        [("strona.html", b"<html></html>"), ("../zrzut.png", b"png"), ("ruch.har", b"{}")],
        "https://przyklad.test/x?a=1",
        tmp_path,
    )
    assert item.id.startswith("upload/") and item.case_id == "upload"
    assert (
        item.paths["html"] and item.paths["har"] and item.paths["screenshot"] and item.paths["url"]
    )
    for rels in item.paths.values():
        for rel in rels:
            assert (tmp_path / rel).exists()
            assert str((tmp_path / rel).resolve()).startswith(str(tmp_path.resolve()))
    url_file = tmp_path / item.paths["url"][0]
    assert url_file.read_text().strip() == "https://przyklad.test/x?a=1"


def test_ingest_upload_without_url_has_no_url_kind(tmp_path):
    item = ingest_upload([("a.html", b"<p>x</p>")], None, tmp_path)
    assert "url" not in item.paths


def test_zip_unpacks_and_blocks_traversal(tmp_path):
    data = make_zip(
        {"s/strona.html": b"<p>x</p>", "s/strona_files/a.png": b"p", "../../zly.html": b"zly"}
    )
    item = ingest_upload([("paczka.zip", data)], None, tmp_path)
    assert len(item.paths["html"]) == 1 and item.paths["html"][0].endswith("strona.html")
    assert item.paths["assets"]
    assert not (tmp_path.parent / "zly.html").exists()
    assert not list(tmp_path.rglob("zly.html"))


def test_zip_limits_and_corrupt_archive(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.ingest.upload.MAX_ZIP_FILES", 2)
    big = make_zip({f"{i}.html": b"x" for i in range(5)})
    item = ingest_upload([("duzo.zip", big)], None, tmp_path)
    assert item.paths == {}
    broken = ingest_upload([("zepsuty.zip", b"to nie zip")], None, tmp_path)
    assert broken.paths == {}


def test_upload_converts_mhtml(tmp_path):
    item = ingest_upload(
        [("zapis.mhtml", build_mhtml("<html><body>A</body></html>"))], None, tmp_path
    )
    assert [Path(p).suffix for p in item.paths["html"]] == [".html"]
    assert item.paths["assets"]


def test_upload_does_not_fetch_by_default(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(fetch, "fetch_page", lambda url, folder: called.append(url))
    ingest_upload([], "https://przyklad.test", tmp_path)
    assert called == []


def test_upload_fetches_only_when_enabled(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(fetch, "fetch_page", lambda url, folder: called.append(url))
    monkeypatch.setenv("MIMIC_ALLOW_FETCH", "1")
    ingest_upload([], "https://przyklad.test", tmp_path)
    assert called == ["https://przyklad.test"]


def test_fetch_refuses_private_hosts_and_bad_schemes(tmp_path):
    assert fetch.fetch_page("http://127.0.0.1/x", tmp_path) is None
    assert fetch.fetch_page("file:///etc/passwd", tmp_path) is None
    assert fetch.fetch_page("ftp://przyklad.test", tmp_path) is None
    assert not fetch.is_public_host("localhost")


def test_fetch_saves_html_with_limit(tmp_path, monkeypatch):
    class Resp:
        def __init__(self, body: bytes, ctype: str = "text/html"):
            self.body, self.headers = body, {"Content-Type": ctype}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return self.body[:n]

    monkeypatch.setattr(fetch, "is_public_host", lambda host: True)
    monkeypatch.setattr(fetch, "_open", lambda url: Resp(b"<html>ok</html>"))
    saved = fetch.fetch_page("https://przyklad.test", tmp_path)
    assert saved is not None and saved.read_bytes() == b"<html>ok</html>"
    monkeypatch.setattr(fetch, "_open", lambda url: Resp(b"x", "application/octet-stream"))
    assert fetch.fetch_page("https://przyklad.test", tmp_path) is None
    monkeypatch.setattr(fetch, "MAX_BYTES", 3)
    monkeypatch.setattr(fetch, "_open", lambda url: Resp(b"<html>za duzo</html>"))
    assert fetch.fetch_page("https://przyklad.test", tmp_path) is None


def test_matches_legacy_discovery_on_real_data():
    raw = Path("data/raw")
    if not raw.is_dir() or not any(raw.iterdir()):
        pytest.skip("brak danych organizatora")
    from app.sources import discover_items as legacy

    new = {i.id: i for i in discover_items(raw)}
    for old in legacy(raw):
        assert old.id in new
        for kind, rels in old.paths.items():
            assert set(rels) <= set(new[old.id].paths.get(kind, []))
