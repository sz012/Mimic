from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app.demo_items import demo_items
from app.graph import graph_html
from app.sources import kind_of, load_items, raw_dir
from engine.cluster import LINK_THRESHOLD, assign, cluster
from engine.cluster.pipeline import all_edges, extract_features
from engine.explain import assignment_card, campaign_card, edge_card
from engine.schema import Edge, Item
from engine.similarity import build_context, compare

CACHE_DIR = Path("data/cache")
UPLOAD_DIR = CACHE_DIR / "uploads"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")

st.set_page_config(page_title="Mimic", layout="wide")


@st.cache_resource(show_spinner="Wyciągam cechy z materiałów…")
def load_corpus(root: str) -> tuple[list[Item], bool]:
    items = load_items()
    if not items:
        return demo_items(), True
    return [extract_features(i, Path(root), CACHE_DIR) for i in items], False


@st.cache_resource(show_spinner="Porównuję materiały parami…")
def corpus_edges(root: str, n: int) -> list[Edge]:
    items, _ = load_corpus(root)
    return all_edges(items, build_context(items))


def evidence_frame(evidence) -> pd.DataFrame:
    rows = []
    for e in evidence:
        rows.append(
            {
                "cecha": e.feature,
                "grupa": e.group,
                "waga": e.weight,
                "zgodność": e.score,
                "wkład": round(e.weight * e.score, 3),
                "lewa strona": _short(e.left),
                "prawa strona": _short(e.right),
                "przesłanka": e.note,
            }
        )
    return pd.DataFrame(rows)


def _short(value) -> str:
    if value is None:
        return "—"
    text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
    return text if len(text) <= 160 else text[:157] + "…"


def show_images(evidence, root: Path) -> None:
    for e in evidence:
        if e.group != "visual" or e.score <= 0:
            continue
        lefts = e.left if isinstance(e.left, list) else [e.left]
        rights = e.right if isinstance(e.right, list) else [e.right]
        pairs = [
            (l, r) for l, r in zip(lefts, rights) if isinstance(l, str) and isinstance(r, str)
        ][:3]
        for left, right in pairs:
            lp, rp = root / left, root / right
            if (
                lp.suffix.lower() in IMAGE_SUFFIXES
                and rp.suffix.lower() in IMAGE_SUFFIXES
                and lp.exists()
                and rp.exists()
            ):
                c1, c2 = st.columns(2)
                c1.image(str(lp), caption=left, width=220)
                c2.image(str(rp), caption=right, width=220)


def show_edge(edge: Edge, root: Path) -> None:
    card = edge_card(edge)
    st.markdown(
        f"**{edge.a} ↔ {edge.b}**: wynik {edge.score:.2f} ({card['strength']}). {card['summary']}"
    )
    for r in card["reasons"]:
        st.markdown(f"- {r}")
    if card["contrary"]:
        st.caption("Przeciw: " + " | ".join(card["contrary"]))
    with st.expander("Wszystkie przesłanki i braki danych"):
        st.dataframe(evidence_frame(edge.evidence), use_container_width=True, hide_index=True)
        st.caption(card["formula"])
        show_images(edge.evidence, root)


def upload_item(files, url: str) -> Item | None:
    if not files and not url:
        return None
    token = uuid.uuid4().hex[:8]
    folder = UPLOAD_DIR / token
    folder.mkdir(parents=True, exist_ok=True)
    paths: dict[str, list[str]] = {}
    for f in files or []:
        target = folder / Path(f.name).name
        target.write_bytes(f.getvalue())
        kind = kind_of(target)
        if kind:
            paths.setdefault(kind, []).append(str(target.relative_to(UPLOAD_DIR)))
    if url:
        (folder / "input.url").write_text(url)
        paths.setdefault("url", []).append(str((folder / "input.url").relative_to(UPLOAD_DIR)))
    item = Item(id=f"upload/{token}", case_id="upload", paths=paths)
    return extract_features(item, UPLOAD_DIR, None)


def main() -> None:
    root = raw_dir()
    st.title("Mimic")
    st.caption(
        "Łączenie podejrzanych reklam i stron w kampanie, z przesłankami dla każdego połączenia."
    )
    with st.sidebar:
        threshold = st.slider("Próg połączenia", 0.3, 0.95, LINK_THRESHOLD, 0.05)
        method = st.radio(
            "Grupowanie",
            ["components", "average"],
            format_func=lambda m: {"components": "składowe grafu", "average": "średnie wiązanie"}[
                m
            ],
        )
        if st.button("Przelicz cechy od nowa"):
            st.cache_resource.clear()
    items, is_demo = load_corpus(str(root))
    if is_demo:
        st.warning(f"Brak materiałów w {root}: pokazuję syntetyczne dane demo.")
    edges = corpus_edges(str(root), len(items))
    campaigns = cluster(items, edges, threshold, method)
    by_id = {i.id: i for i in items}
    real = [c for c in campaigns if not c.is_singleton]
    singles = [c for c in campaigns if c.is_singleton]
    st.sidebar.metric("Materiały", len(items))
    st.sidebar.metric("Kampanie", len(real))
    st.sidebar.metric("Pojedyncze wzorce", len(singles))

    tab_an, tab_camp, tab_graph, tab_feat = st.tabs(
        ["Analiza materiału", "Kampanie", "Graf", "Cechy"]
    )

    with tab_an:
        source = st.radio("Wejście", ["Materiał ze zbioru", "Plik(i)", "URL"], horizontal=True)
        item = None
        if source == "Materiał ze zbioru":
            chosen = st.selectbox("Materiał", [i.id for i in items])
            item = by_id[chosen]
        elif source == "Plik(i)":
            files = st.file_uploader(
                "HTML, HAR, zrzut ekranu, wideo, metadane JSON", accept_multiple_files=True
            )
            if files and st.button("Analizuj pliki"):
                st.session_state["upload_item"] = upload_item(files, "")
            item = st.session_state.get("upload_item")
        else:
            url = st.text_input("Adres URL (nie jest pobierany, strona może być złośliwa)")
            if url and st.button("Analizuj URL"):
                st.session_state["upload_item"] = upload_item([], url)
            item = st.session_state.get("upload_item")
            st.caption(
                "Z samego URL-a cechy liczy moduł infra; bez niego materiał będzie oznaczony jako nowy wzorzec."
            )
        if item is not None:
            ctx = build_context(items)
            assignment = assign(item, campaigns, ctx, threshold=threshold)
            card = assignment_card(assignment)
            if assignment.campaign_id:
                st.success(f"{card['verdict']} (wynik {assignment.score:.2f})")
            else:
                st.info(f"{card['verdict']}, najlepszy wynik {assignment.score:.2f}")
            for r in card["reasons"]:
                st.markdown(f"- {r}")
            sims = []
            for other in items:
                if other.id == item.id:
                    continue
                e = compare(item, other, ctx)
                if e is not None:
                    sims.append(e)
            sims.sort(key=lambda e: -e.score)
            st.subheader("Najbardziej podobne materiały")
            label = {i.id: c.id for c in campaigns for i in c.items}
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "materiał": e.b,
                            "kampania": label.get(e.b),
                            "wynik": e.score,
                            "przesłanki": edge_card(e)["summary"],
                        }
                        for e in sims[:10]
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
            for e in sims[:5]:
                if e.score >= 0.3:
                    show_edge(e, root)

    with tab_camp:
        for c in real:
            card = campaign_card(c.id, c.items, c.edges)
            with st.expander(
                f"Kampania {c.id}: {card['size']} materiałów, przypadki {', '.join(card['cases'])}",
                expanded=True,
            ):
                st.markdown("**Członkowie:** " + ", ".join(card["members"]))
                if card["key_features"]:
                    st.markdown(
                        "**Najczęstsze przesłanki:** "
                        + ", ".join(f"{f} ×{n}" for f, n in card["key_features"])
                    )
                if card["shared_traits"]:
                    st.markdown("**Wspólne ślady:**")
                    for feat, vals in card["shared_traits"].items():
                        st.markdown(f"- `{feat}`: " + ", ".join(f"{v} ({n})" for v, n in vals))
                for e in sorted(c.edges, key=lambda e: -e.score):
                    show_edge(e, root)
        if singles:
            st.subheader("Nowe wzorce (bez kampanii)")
            st.write(", ".join(c.item_ids[0] for c in singles))

    with tab_graph:
        min_edge = st.slider("Pokaż krawędzie od", 0.1, 0.95, 0.3, 0.05)
        components.html(
            graph_html(items, edges, campaigns, min_edge, threshold), height=650, scrolling=False
        )

    with tab_feat:
        chosen = st.selectbox("Materiał", [i.id for i in items], key="feat_item")
        it = by_id[chosen]
        st.json({k: it.paths.get(k) for k in it.kinds})
        rows = [
            {
                "cecha": f.name,
                "grupa": f.group,
                "dostępna": f.available,
                "pewność": f.confidence,
                "źródło": f.source,
                "wartość": _short(
                    f.value
                    if not isinstance(f.value, dict)
                    else {k: v for k, v in f.value.items() if k != "minhash"}
                ),
            }
            for f in it.features.values()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


main()
