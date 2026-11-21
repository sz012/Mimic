# Metodyka

Cel: z pojedynczych materiałów (zapisane strony, logi HAR, zrzuty, nagrania) wydobyć wspólne ślady i połączyć je w kampanie tak, aby każde połączenie dało się wyjaśnić. Poniżej opis przepływu od pliku do kampanii. Szczegóły cech infrastruktury i szablonu: [method-infra.md](method-infra.md).

## 1. Przepływ

1. **Ingest.** Katalogi z plikami zamieniane są na materiały (`Item`): jedna strona to jeden materiał z listą plików według rodzaju (html, har, zrzuty, wideo, metadane, adres, zasoby). Wgrane pliki (także zip i mhtml) są zapisywane bezpiecznie w katalogu roboczym.
2. **Cechy.** Każdy moduł cech zwraca ustrukturyzowane wartości z pewnością i źródłem. Brak danych to jawny brak z powodem, a błąd modułu nie przerywa przetwarzania.
3. **Porównanie.** Dwa materiały porównywane są cecha po cesze, a wyniki łączone w jeden wynik z listą przesłanek.
4. **Grupowanie.** Krawędzie o wyniku powyżej progu tworzą kampanie.
5. **Przypisanie nowego materiału.** Nowy materiał jest porównywany z członkami istniejących kampanii. Najlepsze dopasowanie powyżej progu daje kampanię, w przeciwnym razie wynik to "nowy wzorzec".

## 2. Cechy

| Grupa | Cechy | Sposób |
|---|---|---|
| tekst | dokładny odcisk tekstu, narracja, tytuł, nazwy własne, słowa kluczowe, kwoty, temat, kontakty (e-mail, telefon, komunikator, IBAN) | sygnatura MinHash trigramów słów (128 permutacji), zbiory z miarami Jaccarda i pokrycia, słownik tematów |
| obraz | obrazy z zasobów strony, zrzut ekranu, klatki wideo, dokładny odcisk plików | percepcyjny hash (pHash) i odległość Hamminga, hash SHA-1 dla duplikatów |
| osoby | nazwiska osób publicznych z małej bazy referencyjnej | dopasowanie nazw w tekście strony |
| infrastruktura | domena, hosty, trackery, parametry kampanii, przekierowania, endpointy, favikona, IP, serwer, konto reklamodawcy, metadane domeny (RDAP, DNS, crt.sh) | statyczne parsowanie HAR i HTML, opcjonalne wzbogacenie |
| szablon | odcisk struktury DOM, skrypty, klasy CSS, nazwy zasobów, pola formularzy, komentarze, meta | simhash trigramów znaczników, skróty skryptów po normalizacji identyfikatorów |

Pewność cechy zależy od źródła (HAR najwyższa, sam adres najniższa) i skaluje jej wagę.

## 3. Podobieństwo

Dla pary materiałów, dla każdej cechy dostępnej po obu stronach, komparator zwraca zgodność `s` z przedziału 0..1 i opis po polsku. Wkład cechy to `w × s`, gdzie `w` to waga cechy przeskalowana pewnością (`w = w0 × (0,5 + 0,5 × pewność)`). Wynik pary:

```
wynik = 1 - Π(1 - w_i × s_i)
```

Wzór wzmacnia niezależne dowody, a pojedyncza słaba cecha nie wystarcza do połączenia. Cechy, których brakuje po którejś stronie, nie obniżają wyniku i trafiają do uzasadnienia jako brak danych z powodem.

Komparatory: zbiory wartości (Jaccard i pokrycie), wspólna wartość, MinHash, odległość Hamminga hashy obrazów, odległość odcisków struktury, kosinus wektorów. Wartości pospolite w zbiorze (obecne w ponad połowie materiałów, przy co najmniej sześciu) są ignorowane, aby wspólne biblioteki i usługi nie łączyły niepowiązanych stron.

Wagi startowe: dokładny duplikat tekstu i pliku 0,95; wspólny kontakt 0,9; ta sama narracja 0,8; wspólne obrazy 0,75; podobny zrzut ekranu 0,6; nazwy własne i tytuł 0,45–0,5; słowa kluczowe i kwoty 0,3; temat 0,1. Cechy infrastruktury i szablonu mają wagi domyślne grupy (0,8 i 0,7) do czasu kalibracji. Wagi i próg stroi się na etykietach.

## 4. Ślady platformy i ślady operatora

Wspólna favikona lub ścieżki konstruktora stron dowodzą tej samej platformy, a nie tej samej kampanii. Identyfikatory trackerów (piksel, konto reklamowe), identyfikatory kampanii w adresach, domeny i konta reklamodawców dowodzą tego samego operatora. Wagi i reguły łączenia mają to rozróżniać.

## 5. Grupowanie i przypisanie

- Domyślnie: spójne składowe grafu krawędzi o wyniku co najmniej 0,6. Wariant: średnie wiązanie.
- Kampanie wieloosobowe oznaczane są `K01`, `K02`..., pojedyncze materiały `N..` ("nowy wzorzec").
- Przypisanie nowego materiału: porównanie z każdym członkiem każdej kampanii, wybór najlepszej krawędzi, przypisanie przy wyniku co najmniej 0,6, w przeciwnym razie "nowy wzorzec". Wynik niesie przesłanki najlepszej krawędzi.

## 6. Interpretowalność

Każda krawędź zawiera listę przesłanek: cecha, grupa, waga, zgodność, wartości po obu stronach i opis. Interfejs pokazuje najsilniejsze przesłanki "za", cechy przemawiające "przeciw" (istotne cechy bez wspólnych wartości), braki danych z powodem oraz wzór wyniku.

## 7. Niepełne dane

Martwa strona, sam plik HAR, sam zrzut lub samo wideo dają mniej cech, a nie błąd. Materiał bez żadnych cech nie jest łączony z niczym. Uszkodzone pliki są pomijane.

## 8. Ocena

`make eval` liczy na etykietach z `data/labels/`: precyzję i pokrycie par, ARI, listę fałszywych i pominiętych połączeń, wynik przy różnych progach, ablację grup cech (co się stanie bez danej grupy) oraz test duplikatu (materiał musi połączyć się z własną kopią). Priorytetem jest precyzja: brak fałszywych połączeń.
