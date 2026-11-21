export type DemoStep = { view: string; title: string; description: string; item?: string; other?: string; threshold?: number; sample?: 'known' | 'unknown' }

export const demoSamples = {
  known: '<html><head><title>bankier sekret ujawnia</title></head><body>' + 'platforma inwestycja zysk dzienny rejestracja bankier ujawnia sekret '.repeat(20) + 'Osoba Publiczna 1</body></html>',
  unknown: '<html><head><title>teleskop astronomia galaktyka</title></head><body>' + 'archeologia teleskop astronomia galaktyka orbita muzeum biblioteka nauka '.repeat(20) + '</body></html>',
}

export const demoSteps: DemoStep[] = [
  { view: '/', title: 'Zbiór', description: 'To pojedyncze materiały. Na tym etapie nie zakładamy, które należą do tej samej kampanii.' },
  { view: '/items', title: 'Ślady materiału', description: 'Każdy materiał daje kilka rodzajów śladów. Brak danych pozostaje widoczny.', item: 'demo/A1' },
  { view: '/compare', title: 'Porównanie', description: 'Wynik powstaje z przesłanek. Można sprawdzić, co stanie się bez najważniejszej z nich.', item: 'demo/A1', other: 'demo/A2' },
  { view: '/criteria', title: 'Różne kryteria', description: 'Te same materiały tworzą różne grupy zależnie od pytania, które zadajemy.' },
  { view: '/map', title: 'Mapa kampanii', description: 'Próg decyduje, które powiązania wystarczą do wspólnej kampanii. Kliknij krawędź, by zobaczyć uzasadnienie.', threshold: 0.5 },
  { view: '/new', title: 'Nowy materiał', description: 'Nowy materiał może dołączyć do kampanii, jeśli ma wystarczające wspólne ślady.', sample: 'known' },
  { view: '/new', title: 'Nowy wzorzec', description: 'Gdy dowodów jest za mało, system nie przypisuje materiału na siłę.', sample: 'unknown' },
]
