# Źródła danych, modele i licencje

## Dane i usługi
| Źródło | Do czego | Licencja / warunki | Ograniczenia |
|---|---|---|---|
| Zbiór organizatora (10 przypadków: strony, HAR, zrzuty, wideo, metadane) | rozwój i walidacja | tylko na potrzeby zadania, nie publikować | pliki poza repozytorium, parsowane statycznie |
| RDAP przez rdap.org (przekierowanie do rejestrów) | data rejestracji, rejestrator, serwery nazw | dane publiczne, bez klucza | limity zapytań, różna kompletność, część rejestrów redaguje dane |
| crt.sh (Certificate Transparency) | domeny z tego samego certyfikatu | dane publiczne, bez klucza | wolne, bywa niedostępne; certyfikaty wielodomenowe (powyżej 20 nazw) są pomijane |
| DNS (systemowy resolver) | rekordy A i NS domeny | zapytania do publicznego resolvera | adresy z pul CDN i adresy nieinformatywne są pomijane |
| Meta Ad Library API (`ads_archive`) | wyszukiwanie reklam, konta reklamodawców, okresowe odświeżanie | wymaga tokenu dostępu (konto Meta for Developers, potwierdzona tożsamość, akceptacja warunków Meta Ad Library API); klucza nie przekazujemy w repozytorium | limity zapytań, zakres danych zależy od kraju i typu reklamy. Bez tokenu działa tryb weryfikacji `MIMIC_ADLIB_FIXTURE=1` na wbudowanym, syntetycznym zestawie reklam, bez sieci |
| Lista sufiksów publicznych (wbudowana w tldextract) | domena rejestrowalna | Mozilla Public Suffix List (MPL 2.0) | migawka z chwili wydania pakietu, bez sieci |
| `data/refs/persons.json` | dopasowanie nazwisk osób publicznych | lista nazwisk przygotowana ręcznie na podstawie publicznych ostrzeżeń o oszustwach z wizerunkiem znanych osób; bez obrazów i danych biometrycznych | lista niepełna; nowe osoby dopisuje się w pliku |

Zapytania sieciowe dotyczą wyłącznie nazw domen z danych (oraz metadanych reklam z biblioteki), nigdy samych stron oszustów. Wzbogacenie domen jest domyślnie wyłączone (`MIMIC_ENRICH=0`), a pobieranie stron spod adresu też (`MIMIC_ALLOW_FETCH=0`).

## Biblioteki i modele
| Składnik | Użycie | Licencja | Ograniczenia |
|---|---|---|---|
| fastapi, uvicorn, python-multipart | API interfejsu webowego | MIT, BSD-3-Clause, Apache-2.0 | |
| streamlit, pyvis | zapasowy interfejs i jego graf | Apache-2.0, BSD-3-Clause | zastąpiony głównym interfejsem React |
| networkx | składowe grafu i grupowanie | BSD-3-Clause | |
| React, React DOM, React Router, TanStack Query, Zustand | główny interfejs webowy | MIT | budowany w obrazie Docker (Node 22) |
| D3 (d3-force, d3-selection, d3-zoom i pozostałe moduły) | graf kampanii | ISC | |
| Vite, TypeScript | budowa interfejsu | MIT, Apache-2.0 | |
| Geist (`@fontsource/geist`) | krój pisma interfejsu | SIL Open Font License 1.1 | czcionka dołączona do aplikacji, bez ładowania z sieci |
| beautifulsoup4, lxml | parsowanie HTML | MIT, BSD-3-Clause | |
| pillow, `ImageHash` | obrazy, pHash i dHash | HPND, BSD-2-Clause | pHash wrażliwy na mocne kadrowanie i nakładki |
| `datasketch` | MinHash | MIT | sygnatura przybliża Jaccarda (128 permutacji) |
| tldextract | domena rejestrowalna | BSD-3-Clause | |
| dnspython | zapytania DNS | ISC | |
| pandas, numpy, scikit-learn | tabele i obliczenia | BSD-3-Clause | |
| `opencv-python-headless` (dodatek `video`) | klatki kluczowe wideo | Apache-2.0 | kodeki zależne od kompilacji OpenCV |
| `rapidocr-onnxruntime` (dodatek `ocr`) i modele PP-OCR (PaddleOCR) w ONNX dołączone do pakietu | OCR zrzutów, klatek i obrazów | Apache-2.0 | model rozpoznawania chińsko-angielski: polskie znaki diakrytyczne bywają gubione, więc tekst porównywany jest bez diakrytyków |
| `onnxruntime` | środowisko modeli ONNX | MIT | CPU, ok. 0,5–2 s na obraz, wyniki w pamięci podręcznej |
| `insightface` (dodatek `faces`) i model `buffalo_l` | wykrywanie i rozpoznawanie twarzy osób publicznych z lokalnej bazy referencyjnej | kod: MIT; modele: tylko do niekomercyjnych badań (zgodnie z informacją projektu InsightFace) | model ok. 300 MB pobierany przy pierwszym użyciu (`scripts/fetch_models.py`), CPU. Przed użyciem komercyjnym wymagana zmiana modelu |
| Obrazy referencyjne osób publicznych | baza do dopasowania twarzy w demo | zdjęcia z Wikimedia Commons (CC0, CC BY, CC BY-SA) oraz zdjęcia prasowe i ze stron wydarzeń użyte wyłącznie lokalnie; źródło i licencja każdego zdjęcia w pliku `ZRODLA.txt` obok zdjęć | tylko lokalnie w `data/refs/images/`, poza repozytorium, bez publikowania; to dane biometryczne osób publicznych używane wyłącznie w demo |

Opcjonalne grupy zależności (`video`, `ocr`, `faces`) są instalowane osobno; obraz Docker domyślnie zawiera `video` i `ocr` (`MIMIC_EXTRAS`). Przed włączeniem kolejnego modelu trzeba zapisać tu jego licencję i ograniczenia użycia.
