# Źródła danych: infrastruktura

| Źródło | Do czego | Licencja / warunki | Ograniczenia |
|---|---|---|---|
| Zbiór organizatora (HAR, zapisane strony, metadane) | rozwój i walidacja | tylko na potrzeby zadania, nie publikować | pliki poza repozytorium |
| RDAP przez rdap.org (przekierowanie do rejestrów) | data rejestracji, rejestrator, serwery nazw | dane publiczne, bez klucza | limity zapytań, różna kompletność, część rejestrów redaguje dane |
| crt.sh (Certificate Transparency) | domeny z tego samego certyfikatu | dane publiczne, bez klucza | wolne, bywa niedostępne, certyfikaty wielodomenowe (powyżej 20 nazw) są pomijane |
| DNS (systemowy resolver) | rekordy A i NS domeny | zapytania do publicznego resolvera | adresy z pul CDN i adresy nieinformatywne są pomijane |
| Lista sufiksów publicznych (wbudowana w tldextract) | domena rejestrowalna | Mozilla Public Suffix List (MPL 2.0) | migawka z chwili wydania pakietu, bez sieci |

Zapytania wysyłane są wyłącznie o nazwy domen występujących w danych, nigdy do samych stron. Wzbogacenie jest wyłączone domyślnie (`MIMIC_ENRICH=0`).
