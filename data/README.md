# data/

Dane organizatora są objęte zasadą: tylko na potrzeby zadania, nie publikować. Nie trafiają do gita.

| Ścieżka | W gicie | Zawartość |
|---|---|---|
| `data/raw/<id>/` | nie | 10 przypadków organizatora (1, 2, 3, 5, 10, 14, 36, 47, 48, 61), jeden folder na przypadek, oryginalne nazwy i zawartość, tylko do odczytu |
| `data/cache/` | nie | wyniki ekstrakcji, indeksy, miniatury; do odtworzenia z `data/raw/` |
| `data/labels/` | tak | ręczne przypisanie przypadków do kampanii (ground truth): same identyfikatory i etykiety, bez treści stron |
| `task/` (w korzeniu repo) | nie | PDF-y z opisem zadania |

## Pierwsze uruchomienie po `git clone`

Skopiuj lokalnie (poza gitem), np. z katalogu `materiały`:

```bash
cp -R "../materiały/do_udostępnienia/." data/raw/
```

Drugi członek zespołu dostaje dane od organizatorów albo od Szymona, nie przez GitHub.

## Uwaga bezpieczeństwa

To strony oszustów. Nie otwieraj ich w zwykłej przeglądarce i nie wykonuj ich JS. Parsuj jako statyczne pliki (HTML, HAR, obrazy).
