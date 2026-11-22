export type DemoStep = { view: string; title: string; description: string; item?: string; other?: string; threshold?: number; sample?: 'known' | 'unknown'; analyze?: string; hash?: string }

export const demoSamples = {
  known: '<html><head><title>bankier sekret ujawnia</title></head><body>' + 'platforma inwestycja zysk dzienny rejestracja bankier ujawnia sekret '.repeat(20) + 'Osoba Publiczna 1</body></html>',
  unknown: '<html><head><title>teleskop astronomia galaktyka</title></head><body>' + 'archeologia teleskop astronomia galaktyka orbita muzeum biblioteka nauka '.repeat(20) + '</body></html>',
}

const demoScenario: DemoStep[] = [
  { view: '/', title: 'Wstęp', description: 'Mimic z pojedynczych podejrzanych materiałów odtwarza kampanie oszustw i uzasadnia każde połączenie.' },
  { view: '/collection', title: 'Zbiór', description: 'Zaczynamy od pojedynczych materiałów. Przy każdym widać, ile cech udało się wyciągnąć i ile brakuje.' },
  { view: '/items', title: 'Ślady materiału', description: 'Z materiału wyciągamy tekst, obraz, infrastrukturę, szablon i osoby. Brak danych pozostaje widoczny.', item: 'demo/A1' },
  { view: '/compare', title: 'Dwa materiały jednej kampanii', description: 'Wynik składa się z przesłanek o znanych wagach: tekst, obrazy, osoba.', item: 'demo/A1', other: 'demo/A2' },
  { view: '/', hash: 'mapa', title: 'Mapa kampanii', description: 'Kampanie można definiować na różne sposoby. Przełączaj kryteria i klikaj linie, żeby zobaczyć uzasadnienie.' },
  { view: '/new', title: 'Nowy materiał', description: 'Tu można przeanalizować własny materiał: plik, ZIP lub adres URL, albo wyszukać reklamy w bibliotece reklam.' },
]

const realScenario: DemoStep[] = [
  { view: '/', title: 'Wstęp', description: 'Mimic z pojedynczych podejrzanych materiałów odtwarza kampanie oszustw i uzasadnia każde połączenie.' },
  { view: '/collection', title: 'Zbiór', description: 'Zaczynamy od czternastu pojedynczych materiałów. Przy każdym widać, ile cech udało się wyciągnąć i ile brakuje.' },
  { view: '/items', title: 'Ślady materiału', description: 'Z materiału wyciągamy tekst, obraz, infrastrukturę, szablon i osoby, także po twarzy. Brak danych pozostaje widoczny.', item: '1' },
  { view: '/compare', title: 'Dwa materiały jednej kampanii', description: 'Wynik składa się z przesłanek o znanych wagach: ten sam tracker, identyczny tekst, ta sama twarz.', item: '1', other: '2' },
  { view: '/compare', title: 'Wysoki wynik, a jednak bez połączenia', description: 'Wspólna platforma i te same osoby publiczne nie wystarczą. Bez dowodu na wspólnego operatora system nie łączy.', item: '1', other: '48' },
  { view: '/', hash: 'mapa', title: 'Mapa kampanii', description: 'Kampanie można definiować na różne sposoby. Przełączaj kryteria i klikaj linie, żeby zobaczyć uzasadnienie.' },
  { view: '/new', title: 'Nowy materiał', description: 'Tu można przeanalizować własny materiał: plik, ZIP lub adres URL, albo wyszukać reklamy w bibliotece reklam.' },
]

export function demoStepsFor(ids: string[]): DemoStep[] {
  const known = new Set(ids)
  return ['1', '2', '48'].every(id => known.has(id)) ? realScenario : demoScenario
}
