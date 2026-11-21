from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.brand import load_brand
from app.demo_items import demo_items
from app.graph import graph_html
from app.sources import ingest_upload, load_items, open_store, raw_dir
from engine.cluster import LINK_THRESHOLD, Analysis, Workspace
from engine.explain.report import to_csv, to_html, to_json
from engine.schema import Evidence, Item

CACHE_DIR = Path(os.environ.get("MIMIC_CACHE_DIR", "data/cache"))
UPLOAD_DIR = CACHE_DIR / "uploads"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
METHODS = {"components": "składowe grafu", "average": "średnie wiązanie"}


@st.cache_resource(show_spinner="Wyciągam cechy i porównuję materiały…")
def workspace(root: str) -> tuple[Workspace, bool]:
    items = load_items()
    if not items:
        return Workspace(demo_items(), Path(root)), True
    return Workspace.load(items, Path(root), CACHE_DIR, store=open_store()), False


def short(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "minhash"}
    text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
    return text if len(text) <= 160 else text[:157] + "…"


def evidence_frame(evidence: list[Evidence]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cecha": e.feature,
                "grupa": e.group,
                "waga": e.weight,
                "zgodność": e.score,
                "wkład": round(e.weight * e.score, 3),
                "lewa strona": short(e.left),
                "prawa strona": short(e.right),
                "przesłanka": e.note,
            }
            for e in evidence
        ]
    )


def resolve(rel: str, root: Path) -> Path | None:
    for base in (root, UPLOAD_DIR):
        p = base / rel
        if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file():
            return p
    return None


def show_images(evidence: list[Evidence], root: Path) -> None:
    for e in evidence:
        if e.group != "visual" or e.score <= 0:
            continue
        lefts = e.left if isinstance(e.left, list) else [e.left]
        rights = e.right if isinstance(e.right, list) else [e.right]
        for left, right in list(zip(lefts, rights))[:3]:
            if not (isinstance(left, str) and isinstance(right, str)):
                continue
            lp, rp = resolve(left, root), resolve(right, root)
            if lp and rp:
                c1, c2 = st.columns(2)
                c1.image(str(lp), caption=left, width=220)
                c2.image(str(rp), caption=right, width=220)


def show_edge_card(card: dict, evidence: list[Evidence], root: Path) -> None:
    st.markdown(
        f"**{card['a']} ↔ {card['b']}**: wynik {card['score']:.2f} ({card['strength']}). {card['summary']}"
    )
    st.caption(("Połączone: " if card["linked"] else "Niepołączone: ") + card["basis"])
    for r in card["reasons"]:
        st.markdown(f"- {r}")
    if card["contrary"]:
        st.caption("Przeciw, bo: " + " | ".join(card["contrary"]))
    st.caption("Co musiałoby się zmienić: " + card["counterfactual"])
    with st.expander("Wszystkie przesłanki i braki danych"):
        st.dataframe(evidence_frame(evidence), width="stretch", hide_index=True)
        st.caption(card["formula"])
        show_images(evidence, root)


def show_analysis(analysis: Analysis, root: Path) -> None:
    card = analysis.card
    if card["status"] == "przypisano":
        st.success(f"{card['verdict']} (wynik {card['score']:.2f}). Podstawa: {card['basis']}")
    elif card["status"] == "za_malo_danych":
        st.info(f"{card['verdict']}: {card['basis']}")
    else:
        st.info(f"{card['verdict']}. Najlepszy wynik: {card['score']:.2f}. {card['basis']}")
    if card["runner_up"]:
        st.caption(
            f"Druga najlepsza kampania: {card['runner_up']} ({analysis.detail.runner_up_score:.2f})"
        )
    if analysis.best_edge_card:
        st.caption("Co musiałoby się zmienić: " + analysis.best_edge_card["counterfactual"])
    st.caption(analysis.formula)
    if card["reasons"]:
        st.markdown("**Przesłanki najlepszego dopasowania:**")
        for r in card["reasons"]:
            st.markdown(f"- {r}")
    if analysis.missing:
        with st.expander(f"Czego brakowało w tym materiale ({len(analysis.missing)} cech)"):
            st.dataframe(pd.DataFrame(analysis.missing), width="stretch", hide_index=True)
    st.subheader("Najbardziej podobne materiały")
    if not analysis.similar:
        st.write("Brak materiałów z jakąkolwiek wspólną przesłanką.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "materiał": r["item"],
                    "kampania": r["campaign"],
                    "wynik": r["score"],
                    "przesłanki": r["card"]["summary"],
                }
                for r in analysis.similar
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    for r in analysis.similar[:5]:
        if r["score"] >= 0.3:
            show_edge_card(r["card"], r["edge"].evidence, root)


def run_upload(files: list[tuple[str, bytes]], url: str | None) -> None:
    try:
        item = ingest_upload(files, url, UPLOAD_DIR)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not item.paths:
        st.warning(
            "Nie rozpoznano żadnego pliku (obsługiwane: html, har, zrzuty, wideo, json, url, zip)."
        )
        return
    st.session_state["upload_item"] = item


def analysis_tab(ws: Workspace, root: Path) -> None:
    source = st.radio("Wejście", ["Materiał ze zbioru", "Pliki", "URL"], horizontal=True)
    if source == "Materiał ze zbioru":
        chosen = st.selectbox("Materiał", [i.id for i in ws.items])
        show_analysis(ws.analyze(ws.by_id[chosen]), root)
        return
    if source == "Pliki":
        files = st.file_uploader(
            "HTML, HAR, zrzuty ekranu, wideo, metadane JSON albo archiwum ZIP",
            accept_multiple_files=True,
        )
        if files and st.button("Analizuj pliki"):
            run_upload([(f.name, f.getvalue()) for f in files], None)
    else:
        url = st.text_input("Adres URL (nie jest pobierany, strona może być złośliwa)")
        st.caption(
            "Sam adres trafia do cech infrastruktury; bez nich materiał zostanie oznaczony jako nowy wzorzec."
        )
        if url and st.button("Analizuj URL"):
            run_upload([], url)
    item: Item | None = st.session_state.get("upload_item")
    if item is None:
        return
    show_analysis(ws.analyze(item, UPLOAD_DIR), root)
    if item.id not in ws.by_id and st.button("Dodaj do zbioru i przelicz kampanie"):
        assignment = ws.add(item, UPLOAD_DIR)
        st.success(f"Dodano {item.id}. Przypisanie: {assignment.campaign_id or 'nowy wzorzec'}")


def campaigns_tab(ws: Workspace, root: Path) -> None:
    cards = ws.campaign_cards()
    for card in cards:
        title = (
            f"Kampania {card['id']}: {card['size']} materiały, przypadki {', '.join(card['cases'])}"
        )
        with st.expander(title, expanded=True):
            st.markdown("**Członkowie:** " + ", ".join(card["members"]))
            if card["links"]:
                st.markdown("**Co je łączy:**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "przesłanka": r["label"],
                                "grupa": r["group"],
                                "połączeń": r["edges"],
                                "mocnych": r["strong"],
                                "przykład": r["example"],
                            }
                            for r in card["links"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            if card["shared_traits"]:
                st.markdown("**Wspólne ślady:**")
                for feat, vals in card["shared_traits"].items():
                    st.markdown(f"- `{feat}`: " + ", ".join(f"{v} ({n})" for v, n in vals))
            if card["missing"]:
                st.markdown(
                    "**Brakujące dane:** "
                    + "; ".join(
                        f"{m['feature']} ({len(m['items'])}/{card['size']})"
                        for m in card["missing"]
                    )
                )
            campaign = ws.campaign(card["id"])
            for edge, ecard in zip(sorted(campaign.edges, key=lambda e: -e.score), card["edges"]):
                show_edge_card(ecard, edge.evidence, root)
    if ws.singletons:
        st.subheader("Nowe wzorce (bez kampanii)")
        st.write(", ".join(c.item_ids[0] for c in ws.singletons))
    history = ws.history()
    if history:
        st.subheader("Zapisane przypisania dodanych materiałów")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "materiał": a.item_id,
                        "kampania": a.campaign_id or "nowy wzorzec",
                        "kampania teraz": ws.label.get(a.item_id),
                        "wynik": a.score,
                    }
                    for a in history
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    meta = {
        **ws.stats(),
        "threshold": ws.threshold,
        "method": METHODS[ws.method],
        "formula": cards[0]["formula"] if cards else "",
    }
    st.subheader("Eksport")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Raport JSON", to_json(cards, meta), "kampanie.json", "application/json")
    c2.download_button("Tabela CSV", to_csv(cards), "kampanie.csv", "text/csv")
    c3.download_button("Raport HTML do wydruku", to_html(cards, meta), "kampanie.html", "text/html")


def graph_tab(ws: Workspace) -> None:
    min_edge = st.slider("Pokaż krawędzie od", 0.1, 0.95, 0.3, 0.05)
    st.caption(
        "Kolor węzła = kampania (szary: nowy wzorzec), grubość krawędzi = wynik, linia przerywana = poniżej progu."
    )
    st.iframe(graph_html(ws.graph(min_edge), load_brand()), height=650)


def features_tab(ws: Workspace) -> None:
    chosen = st.selectbox("Materiał", [i.id for i in ws.items], key="feat_item")
    it = ws.by_id[chosen]
    st.json({k: it.paths.get(k) for k in it.kinds})
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "cecha": f.name,
                    "grupa": f.group,
                    "dostępna": f.available,
                    "pewność": f.confidence,
                    "źródło": f.source,
                    "wartość": short(f.value),
                }
                for f in sorted(it.features.values(), key=lambda f: f.name)
            ]
        ),
        width="stretch",
        hide_index=True,
    )


def main() -> None:
    st.set_page_config(page_title="Mimic", layout="wide")
    root = raw_dir()
    st.title("Mimic")
    st.caption(
        "Łączenie podejrzanych reklam i stron w kampanie, z przesłankami dla każdego połączenia."
    )
    ws, is_demo = workspace(str(root))
    with st.sidebar:
        threshold = st.slider("Próg połączenia", 0.3, 0.95, LINK_THRESHOLD, 0.05)
        method = st.radio("Grupowanie", list(METHODS), format_func=METHODS.get)
        case_links = st.checkbox(
            "Łącz materiały z tego samego przypadku",
            value=True,
            help="Reklama i strony docelowe z jednego zgłoszenia trafiają do jednej kampanii.",
        )
        if st.button("Przelicz cechy od nowa"):
            st.cache_resource.clear()
            st.rerun()
    if (threshold, method, case_links) != (ws.threshold, ws.method, ws.case_links):
        ws.recluster(threshold, method, case_links)
    if is_demo:
        st.warning(f"Brak materiałów w {root}: pokazuję syntetyczne dane demo.")
    stats = ws.stats()
    st.sidebar.metric("Materiały", stats["items"])
    st.sidebar.metric("Kampanie", stats["campaigns"])
    st.sidebar.metric("Nowe wzorce", stats["singletons"])
    if stats["insufficient"]:
        st.sidebar.metric("Za mało danych", stats["insufficient"])
    tab_an, tab_camp, tab_graph, tab_feat = st.tabs(
        ["Analiza materiału", "Kampanie", "Graf", "Cechy"]
    )
    with tab_an:
        analysis_tab(ws, root)
    with tab_camp:
        campaigns_tab(ws, root)
    with tab_graph:
        graph_tab(ws)
    with tab_feat:
        features_tab(ws)


main()
