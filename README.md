# Mimic

Narzędzie do zadania NASK "Follow the Fake" (HackNation 2026). Z pojedynczych podejrzanych reklam i stron wydobywa wspólne ślady (tekst, szablon, infrastruktura, obraz, osoby) i łączy je w kampanie. Każde połączenie ma listę przesłanek. Nowy materiał jest przypisywany do istniejącej kampanii albo oznaczany jako "nowy wzorzec".

## Uruchomienie

Wymagane: Python 3.12 i [uv](https://docs.astral.sh/uv/).

```bash
make setup
```

```bash
make run
```

Aplikacja działa pod adresem http://localhost:8501.

Interfejs React działa osobno z API. Uruchom serwer przez `make api` (port 8000), a w drugim terminalu `cd web && npm ci && npm run dev` (port 5173). W produkcji FastAPI podaje też zbudowaną aplikację pod portem 8000.

```bash
docker compose up --build web
```

Docker (bez instalowania Pythona):

```bash
docker compose up --build
```

Dane organizatora nie są w repozytorium. Jak je umieścić: [data/README.md](data/README.md). Bez danych aplikacja się uruchamia, a materiały można wgrywać w interfejsie.

## Polecenia

| Polecenie | Działanie |
|---|---|
| `make setup` | instalacja zależności z `uv.lock` |
| `make run` | uruchomienie aplikacji Streamlit |
| `make ingest` | odkrycie materiałów w `data/raw/`, policzenie cech, zapis w bazie SQLite |
| `make eval` | ocena grupowania na etykietach z `data/labels/` (precyzja, pokrycie, ARI, test "nie łącz") |
| `make refresh` | wyszukanie reklam w bibliotece reklam Meta (wymaga tokenu), dopisanie do bazy i przypisanie do kampanii |
| `make labels-check` | sprawdzenie, że etykiety odpowiadają materiałom na dysku |
| `make test` | testy |

## Konfiguracja

Zmienne środowiskowe (wzór w `.env.example`, plik `.env` nie trafia do gita):

| Zmienna | Znaczenie | Domyślnie |
|---|---|---|
| `MIMIC_RAW_DIR` | katalog z materiałami | `data/raw` |
| `MIMIC_CACHE_DIR` | cache cech i wzbogacenia | `data/cache` |
| `MIMIC_DB_PATH` | baza SQLite | `data/cache/mimic.sqlite` |
| `MIMIC_LABELS` | plik etykiet do oceny | `data/labels/labels.json` |
| `MIMIC_ENRICH` | `1` włącza zapytania o metadane domen (RDAP, DNS, crt.sh) | `0` |
| `MIMIC_ALLOW_FETCH` | `1` pozwala pobrać stronę spod podanego URL (statycznie, bez JS) | `0` |
| `META_AD_LIBRARY_TOKEN` | token dostępu do biblioteki reklam Meta (bez niego odświeżanie zgłasza brak) | puste |
| `MIMIC_ADLIB_QUERIES` | frazy wyszukiwania oddzielone przecinkami, np. `inwestycje,suplement` | puste |
| `MIMIC_ADLIB_COUNTRIES` | kraje docelowe reklam | `PL` |
| `MIMIC_REFRESH_SECONDS` | odstęp między odświeżeniami w trybie ciągłym | `21600` |
| `MIMIC_EXTRAS` | dodatkowe grupy zależności w obrazie Docker, np. `video,faces` | puste |
| `MIMIC_MODELS_DIR` | katalog modeli | `models` |

## Okresowe odświeżanie z biblioteki reklam

```bash
docker compose --profile refresh up -d refresher
```

Usługa co `MIMIC_REFRESH_SECONDS` pobiera reklamy dla zapytań z `MIMIC_ADLIB_QUERIES`, wylicza cechy, przypisuje nowe reklamy do istniejących kampanii albo oznacza je jako nowy wzorzec i zapisuje wynik w bazie. Pobierane są tylko metadane reklam (tekst, strona reklamodawcy, domena docelowa), nigdy strony oszustów.

## Bezpieczeństwo

Materiały to oszukańcze strony. Nie otwieraj ich w przeglądarce. Narzędzie parsuje je jako statyczne pliki (HTML, HAR, obrazy) i nie wykonuje ich skryptów. Zapytania sieciowe dotyczą wyłącznie publicznych metadanych domen i są domyślnie wyłączone.

## Struktura

- `app/` demonstrator (Streamlit)
- `engine/` logika bez zależności od interfejsu: `ingest`, `features`, `similarity`, `cluster`, `store`, `explain`, `enrich`
- `eval/` metryki i ocena
- `data/labels/` etykiety kampanii (jedyna część `data/` w gicie)
- `docs/` metodyka, źródła danych, decyzje

## Dokumentacja

- [Metodyka](docs/methodology.md): cechy, podobieństwo, grupowanie
- [Źródła danych i licencje](docs/data-sources.md)
- [Decyzje projektowe](docs/decisions.md)
