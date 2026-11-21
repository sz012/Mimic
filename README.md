# Mimic

Narzędzie do zadania NASK "Follow the Fake" (HackNation 2026). Z pojedynczych podejrzanych reklam i stron wydobywa wspólne ślady (tekst, szablon, infrastruktura, obraz, osoby) i łączy je w kampanie. Każde połączenie ma listę przesłanek.

## Uruchomienie

```bash
make setup   # uv sync
make run     # Streamlit na http://localhost:8501
```

Docker:

```bash
docker compose up --build
```

Dane organizatora znajdują się poza repo.

## Struktura

- `app/` demonstrator (Streamlit)
- `engine/` logika bez zależności od UI: `ingest`, `features`, `similarity`, `cluster`, `store`, `explain`
- `eval/` metryki i skrypt `run_eval.py`
- `docs/` metodyka, źródła danych, decyzje

## Testy

```bash
make test
make eval
```
