import json
from pathlib import Path

import pytest

from engine.sources import AdLibraryUnavailable, AdQuery, materialize, search
from engine.sources.adlib import GRAPH_HOST, ad_document
from engine.store import Store
from scripts.refresh import run_once


def ad(
    ad_id: str, title: str, body: str, caption: str = "przyklad.test", page="Strona Testowa"
) -> dict:
    return {
        "id": ad_id,
        "page_id": "555",
        "page_name": page,
        "ad_creative_bodies": [body],
        "ad_creative_link_titles": [title],
        "ad_creative_link_captions": [caption],
        "ad_delivery_start_time": "2026-10-01",
        "publisher_platforms": ["facebook"],
    }


class FakeTransport:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        return self.pages.pop(0)


STORY = (
    "Znany ekspert ujawnia sekretną platformę inwestycyjną, która pozwala zarabiać codziennie. "
    "Wystarczy rejestracja i niewielka wpłata, a algorytm sam pomnaża kapitał bez ryzyka dla klienta. "
    "Tysiące osób już skorzystało, a banki próbują ukryć tę metodę przed zwykłymi ludźmi w całym kraju."
)
OTHER = (
    "Nowy suplement na stawy łagodzi ból już po tygodniu stosowania według opinii pacjentów z wielu miast. "
    "Kapsułki zawierają naturalne składniki, a promocja obowiązuje tylko dziś przy zamówieniu przez formularz."
)


def test_search_requires_token(monkeypatch):
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    with pytest.raises(AdLibraryUnavailable):
        search(AdQuery("inwestycje"), FakeTransport([]))


def test_search_sends_token_in_header_not_in_url_and_follows_paging():
    page1 = {
        "data": [ad("1000001", "t", "b")],
        "paging": {"next": f"https://{GRAPH_HOST}/next?x=1"},
    }
    page2 = {"data": [ad("1000002", "t", "b")]}
    transport = FakeTransport([page1, page2])
    ads = search(AdQuery("inwestycje", ["PL"]), transport, access_token="SEKRET")
    assert [a["id"] for a in ads] == ["1000001", "1000002"]
    assert all(h == {"Authorization": "Bearer SEKRET"} for _, h in transport.calls)
    assert all("SEKRET" not in url for url, _ in transport.calls)
    assert "search_terms=inwestycje" in transport.calls[0][0]


def test_search_ignores_foreign_paging_hosts_and_respects_max_pages():
    foreign = {"data": [ad("1000001", "t", "b")], "paging": {"next": "https://zly.test/next"}}
    transport = FakeTransport([foreign, foreign])
    assert len(search(AdQuery("x"), transport, access_token="t")) == 1
    assert len(transport.calls) == 1
    loop = {"data": [ad("1000003", "t", "b")], "paging": {"next": f"https://{GRAPH_HOST}/n"}}
    transport = FakeTransport([loop, loop, loop, loop])
    assert len(search(AdQuery("x", max_pages=2), transport, access_token="t")) == 2


def test_search_wraps_network_errors():
    class Broken:
        def get(self, url, headers=None):
            raise OSError("brak sieci")

    with pytest.raises(AdLibraryUnavailable) as err:
        search(AdQuery("x"), Broken(), access_token="SEKRET")
    assert "SEKRET" not in str(err.value)


def test_ad_document_uses_keys_read_by_extractors_and_drops_snapshot_token():
    document = ad_document(
        {
            **ad("1000001", "Tytuł", "Treść reklamy"),
            "ad_snapshot_url": "https://x/?access_token=ZZZ",
        }
    )
    assert document["title"] == "Tytuł" and "Treść" in document["description"]
    assert document["extractor"] == "facebook:ads" and document["uploader"] == "Strona Testowa"
    assert document["page_url"] == "https://przyklad.test/"
    assert "ZZZ" not in json.dumps(document)
    assert "page_url" not in ad_document(ad("1000001", "t", "b", caption="nie domena z spacjami"))


def test_materialize_writes_files_and_skips_bad_ids(tmp_path):
    items = materialize([ad("1000001", "t", "b"), ad("../zly", "t", "b")], tmp_path)
    assert [i.id for i in items] == ["adlib/1000001"]
    assert items[0].paths == {"meta": ["1000001/ad.json"]}
    assert (tmp_path / "1000001" / "ad.json").exists()
    assert not list(tmp_path.glob("**/zly*"))


def test_run_once_assigns_to_existing_campaign_or_marks_new_pattern(tmp_path, monkeypatch):
    monkeypatch.setenv("META_AD_LIBRARY_TOKEN", "t")
    store = Store(tmp_path / "db.sqlite")
    root, cache = tmp_path / "adlib", tmp_path
    first = FakeTransport(
        [
            {
                "data": [
                    ad("1000001", "Sekretna platforma", STORY),
                    ad("1000002", "Sekretna platforma", STORY),
                ]
            }
        ]
    )
    summary = run_once(["x"], ["PL"], 1, store, root, cache, transport=first)
    assert summary["new"] == 2
    assert len(store.campaigns()) == 1
    second = FakeTransport(
        [
            {
                "data": [
                    ad("1000003", "Sekretna platforma", STORY),
                    ad(
                        "1000004",
                        "Suplement na stawy",
                        OTHER,
                        caption="inna.test",
                        page="Inna Strona",
                    ),
                ]
            }
        ]
    )
    summary = run_once(["x"], ["PL"], 1, store, root, cache, transport=second)
    assert summary == {"fetched": 2, "new": 2, "assigned": 1}
    got = {a.item_id: a for a in store.assignments()}
    assert got["adlib/1000003"].campaign_id is not None and got["adlib/1000003"].evidence
    assert got["adlib/1000004"].is_new_pattern
    again = FakeTransport([{"data": [ad("1000003", "Sekretna platforma", STORY)]}])
    assert run_once(["x"], ["PL"], 1, store, root, cache, transport=again)["new"] == 0


def test_run_once_without_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    with pytest.raises(AdLibraryUnavailable):
        run_once(["x"], ["PL"], 1, Store(tmp_path / "d.sqlite"), tmp_path / "a", tmp_path)


def test_items_carry_infra_and_text_features(tmp_path):
    from engine.cluster.pipeline import extract_features

    item = materialize([ad("1000001", "Tytuł reklamy", STORY)], tmp_path)[0]
    extract_features(item, tmp_path, None)
    assert item.features["infra.ad_account"].value == ["facebook:strona testowa"]
    assert item.features["infra.domain"].value == ["przyklad.test"]
    assert item.features["text.narrative"].available
    assert Path(tmp_path / "1000001" / "ad.json").exists()
