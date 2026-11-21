export type DemoStep = { view: string; title: string; description: string; item?: string; other?: string; threshold?: number; sample?: 'known' | 'unknown'; analyze?: string; hash?: string }

export const demoSamples = {
  known: '<html><head><title>bankier sekret ujawnia</title></head><body>' + 'platforma inwestycja zysk dzienny rejestracja bankier ujawnia sekret '.repeat(20) + 'Osoba Publiczna 1</body></html>',
  unknown: '<html><head><title>teleskop astronomia galaktyka</title></head><body>' + 'archeologia teleskop astronomia galaktyka orbita muzeum biblioteka nauka '.repeat(20) + '</body></html>',
}

const demoScenario: DemoStep[] = [
  { view: '/', title: 'Efekt końcowy', description: 'Mapa kampanii: ramki to kampanie, linie to powiązania z uzasadnieniem. Zaraz rozłożymy to na czynniki pierwsze.' },
  { view: '/collection', title: 'Zbiór', description: 'Zaczynamy od pojedynczych materiałów. Na tym etapie nie zakładamy, które należą do tej samej kampanii.' },
  { view: '/items', title: 'Ślady materiału', description: 'Z materiału wyciągamy tekst, obraz, infrastrukturę, szablon i osoby, także po twarzy. Brak danych pozostaje widoczny.', item: 'demo/A1' },
  { view: '/compare', title: 'Dwa materiały jednej kampanii', description: 'Wynik składa się z przesłanek o znanych wagach: ten sam tracker, ten sam tekst, ta sama twarz.', item: 'demo/A1', other: 'demo/A2' },
  { view: '/criteria', title: 'Po czym dzielić na kampanie', description: 'Te same materiały tworzą różne grupy zależnie od kryterium. Żadne samo nie wystarcza, dopiero razem.' },
  { view: '/', hash: 'mapa', title: 'Mapa kampanii', description: 'Próg decyduje, które powiązania wystarczą do wspólnej kampanii. Kliknij linię, żeby zobaczyć uzasadnienie.' },
  { view: '/new', title: 'Nowy materiał trafia do kampanii', description: 'Nowy materiał jest porównywany z całym zbiorem i przypisany tam, gdzie ma dowody.', sample: 'known' },
  { view: '/new', title: 'Nowy wzorzec', description: 'Gdy dowodów jest za mało, system nie przypisuje materiału na siłę.', sample: 'unknown' },
]

const realScenario: DemoStep[] = [
  { view: '/', title: 'Efekt końcowy', description: 'Mapa kampanii: ramki to kampanie, linie to powiązania z uzasadnieniem. Zaraz rozłożymy to na czynniki pierwsze.' },
  { view: '/collection', title: 'Zbiór', description: 'Zaczynamy od pojedynczych materiałów. Na tym etapie nie zakładamy, które należą do tej samej kampanii.' },
  { view: '/items', title: 'Ślady materiału', description: 'Z materiału wyciągamy tekst, obraz, infrastrukturę, szablon i osoby, także po twarzy. Brak danych pozostaje widoczny.', item: '1' },
  { view: '/compare', title: 'Dwa materiały jednej kampanii', description: 'Wynik składa się z przesłanek o znanych wagach: ten sam tracker, ten sam tekst, ta sama twarz.', item: '1', other: '2' },
  { view: '/compare', title: 'Te same twarze, a jednak osobne kampanie', description: 'Te same osoby i podobne narzędzia nie wystarczą. Bez dowodu na wspólnego operatora system nie łączy, bo ważna jest precyzja.', item: '1', other: '48' },
  { view: '/criteria', title: 'Po czym dzielić na kampanie', description: 'Te same materiały tworzą różne grupy zależnie od kryterium. Żadne samo nie wystarcza, dopiero razem.' },
  { view: '/', hash: 'mapa', title: 'Mapa kampanii', description: 'Próg decyduje, które powiązania wystarczą do wspólnej kampanii. Kliknij linię, żeby zobaczyć uzasadnienie.' },
  { view: '/new', title: 'Nowy materiał trafia do kampanii', description: 'Materiał jest porównywany z resztą zbioru i przypisany tam, gdzie ma dowody. Pokazujemy to na materiale, którego system nie zna.', analyze: '3' },
  { view: '/new', title: 'Nowy wzorzec', description: 'Gdy dowodów jest za mało, system nie przypisuje materiału na siłę.', analyze: '47' },
]

export function demoStepsFor(ids: string[]): DemoStep[] {
  const known = new Set(ids)
  return ['1', '2', '3', '47', '48'].every(id => known.has(id)) ? realScenario : demoScenario
}
