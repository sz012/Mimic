# Źródła danych i licencje

## Dane
| Źródło | Do czego | Licencja / warunki | Ograniczenia |
|---|---|---|---|
| Zbiór organizatora (10 przypadków: strony, HAR, zrzuty, wideo, metadane) | rozwój i walidacja | tylko na potrzeby zadania | nie publikować; pliki poza repozytorium |
| RDAP przez rdap.org | data rejestracji, rejestrator, serwery nazw | dane publiczne | limity zapytań, różna kompletność |
| crt.sh (Certificate Transparency) | domeny z tego samego certyfikatu | dane publiczne | wolne, bywa niedostępne; certyfikaty wielodomenowe pomijane |
| DNS (systemowy resolver) | rekordy A i NS | zapytania do publicznego resolvera | adresy CDN pomijane |
| Meta Ad Library API (`ads_archive`) | wyszukiwanie reklam i konta reklamodawców, okresowe odświeżanie | wymaga tokenu dewelopera i akceptacji warunków Meta Ad Library API | limity zapytań, zakres danych zależy od kraju i typu reklamy; bez tokenu funkcja jest wyłączona |
| Lista sufiksów publicznych (wbudowana w tldextract) | domena rejestrowalna | Mozilla Public Suffix List (MPL 2.0) | migawka z chwili wydania pakietu |
| Lista osób publicznych w `engine/features/person.py` | dopasowanie nazwisk | ręcznie wpisane nazwy, bez zdjęć | mała baza |

Zapytania sieciowe dotyczą wyłącznie nazw domen z danych, nigdy samych stron, i są domyślnie wyłączone (`MIMIC_ENRICH=0`). Szczegóły infrastruktury: [data-sources-infra.md](data-sources-infra.md).

## Biblioteki
| Biblioteka | Użycie | Licencja |
|---|---|---|
| streamlit | interfejs | Apache-2.0 |
| networkx, pyvis | grupowanie i graf | BSD-3-Clause |
| beautifulsoup4, lxml | parsowanie HTML | MIT, BSD-3-Clause |
| pillow, imagehash | obrazy i percepcyjny hash | HPND, BSD-2-Clause |
| datasketch | MinHash | MIT |
| tldextract | domena rejestrowalna | BSD-3-Clause |
| dnspython | zapytania DNS | ISC |
| pandas, numpy, scikit-learn | tabele i obliczenia | BSD-3-Clause |

Opcjonalne grupy zależności (`video`, `faces`, `ml`) są instalowane osobno. Przed ich włączeniem trzeba zapisać tu licencję modelu i ograniczenia użycia.
