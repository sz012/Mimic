from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "main.py")


def test_app_runs_on_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_RAW_DIR", str(tmp_path / "pusty"))
    monkeypatch.setenv("MIMIC_CACHE_DIR", str(tmp_path / "cache"))
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert any("demo" in w.value for w in at.warning)
    at.sidebar.slider[0].set_value(0.9).run()
    assert not at.exception


def test_app_runs_on_files(raw, tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_RAW_DIR", str(raw))
    monkeypatch.setenv("MIMIC_DB_PATH", str(tmp_path / "mimic.sqlite"))
    monkeypatch.setenv("MIMIC_CACHE_DIR", str(tmp_path / "cache"))
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert not at.warning
    assert at.sidebar.metric[0].value == "4"
    next(r for r in at.radio if r.label == "Wejście").set_value("URL").run()
    at.text_input[0].set_value("https://przyklad.test/x").run()
    next(b for b in at.button if b.label == "Analizuj URL").click().run()
    assert any("nowy wzorzec" in i.value or "za mało danych" in i.value for i in at.info)
    assert not at.exception


def test_adlib_tab_without_token(raw, tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_RAW_DIR", str(raw))
    monkeypatch.setenv("MIMIC_DB_PATH", str(tmp_path / "mimic.sqlite"))
    monkeypatch.setenv("MIMIC_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(r for r in at.radio if r.label == "Wejście").set_value("Biblioteka reklam").run()
    assert not at.exception
    assert any("META_AD_LIBRARY_TOKEN" in i.value for i in at.info)
