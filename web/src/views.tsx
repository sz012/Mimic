import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import anatomyStyles from './Anatomy.module.css'
import { demoSamples } from './demo/script'
import { faceMatches, featureLabel, post, request, short, groups, groupNames } from './api'
import { CampaignGraph, edgeKey, shortId } from './Graph'
import type { Selection } from './Graph'
import type { Analysis, AppState, Campaign, Comparison, Criteria, EdgeCard, Feature, Graph, Group, ItemDetail, ItemRow } from './api'
import { CampaignChip, Card, Confidence, EdgeDetails, Empty, GroupChip, ItemLink, Score, Section } from './ui'

function useItems() { return useQuery({ queryKey: ['items'], queryFn: () => request<ItemRow[]>('/items') }) }
function useStateData() { return useQuery({ queryKey: ['state'], queryFn: () => request<AppState>('/state') }) }
function useCampaigns() { return useQuery({ queryKey: ['campaigns'], queryFn: () => request<Campaign[]>('/campaigns') }) }

function primaryImage(item?: ItemDetail): string | null {
  const screenshot = item?.features.find(feature => feature.name === 'visual.screenshot')
  if (!Array.isArray(screenshot?.value)) return null
  const image = screenshot.value.find(entry => entry && typeof entry === 'object' && 'src' in entry) as { src: string } | undefined
  return image?.src || null
}

function ImagePair({ first, second, firstLabel, secondLabel }: { first: string | null; second: string | null; firstLabel: string; secondLabel: string }) {
  if (!first && !second) return null
  return <div className="imagePair">{[[first, firstLabel], [second, secondLabel]].map(([path, label]) => {
    const source = path ? `/api/media?path=${encodeURIComponent(path)}` : null
    return <figure key={label} className="imageTile">{source && <span className="imageBackdrop" style={{ backgroundImage: `url("${source}")` }} aria-hidden="true" />}<figcaption>{label}</figcaption>{source ? <img src={source} alt={`Obraz źródłowy: ${label}`} /> : <p>Brak zrzutu</p>}</figure>
  })}</div>
}

export function Collection() {
  const { data: items = [] } = useItems()
  const { data: state } = useStateData()
  const [campaign, setCampaign] = useState('')
  const [caseId, setCaseId] = useState('')
  const cases = [...new Set(items.map(item => item.case_id))].sort()
  const campaigns = [...new Set(items.map(item => item.campaign).filter(Boolean))] as string[]
  const filtered = items.filter(item => (!campaign || item.campaign === campaign) && (!caseId || item.case_id === caseId))
  return <Section title="Zbiór materiałów" lead="Punkt wyjścia do analizy. Każdy wiersz to jeden materiał i jego dostępne ślady." action={state?.is_demo && <span className="demoBadge">Dane demonstracyjne</span>}>
    <div className="statsGrid"><Card><b>{state?.stats.items ?? '-'}</b><span>materiałów</span></Card><Card><b>{state?.stats.campaigns ?? '-'}</b><span>kampanii</span></Card><Card><b>{state?.stats.singletons ?? '-'}</b><span>pojedynczych wzorców</span></Card><Card><b>{state?.stats.insufficient ?? '-'}</b><span>z niedostatecznymi danymi</span></Card></div>
    <div className="filters"><label>Kampania<select value={campaign} onChange={event => setCampaign(event.target.value)}><option value="">Wszystkie</option>{campaigns.map(id => <option key={id}>{id}</option>)}</select></label><label>Przypadek<select value={caseId} onChange={event => setCaseId(event.target.value)}><option value="">Wszystkie</option>{cases.map(id => <option key={id}>{id}</option>)}</select></label></div>
    {filtered.length ? <div className="itemGrid">{filtered.map(item => <Link className="itemCard card" to={`/items/${encodeURIComponent(item.id)}`} key={item.id}><div className="itemCardTop"><span className="fileKinds">{item.kinds.join(' · ') || 'bez pliku'}</span><CampaignChip campaign={item.campaign} singleton={item.singleton} /></div><h2>{item.id}</h2><p>Przypadek {item.case_id}</p><div className="featureCounts"><span>{item.available_features} dostępnych cech</span><span>{item.missing_features} brakujących</span></div></Link>)}</div> : <Empty>Brak materiałów dla wybranych filtrów.</Empty>}
  </Section>
}

function FeatureValue({ feature }: { feature: Feature }) {
  const [expanded, setExpanded] = useState(false)
  if (!feature.available) return <p className="missingValue">Brak danych: {feature.source || 'materiał nie zawiera tej cechy'}</p>
  const value = short(feature.value, expanded ? 2000 : 130)
  const faces = feature.name === 'person.faces' ? faceMatches(feature.value) : null
  const faceCount = feature.name === 'person.face_vectors' && feature.value && typeof feature.value === 'object' && 'count' in feature.value ? Number(feature.value.count) : null
  const images = feature.name === 'visual.screenshot' && Array.isArray(feature.value) ? feature.value.flatMap(entry => entry && typeof entry === 'object' && 'src' in entry ? [String(entry.src)] : []) : []
  return <>
    {faces ? <><div className="chips">{faces.map((face, index) => <span className="faceChip" key={index}>{face.label}{face.score !== undefined ? ` · ${Math.round(face.score * 100)}%` : ''}</span>)}</div><small>Pewność najlepszego dopasowania: {Math.round(feature.confidence * 100)}%</small></> : <p className="featureValue">{faceCount === null ? value : `Wykryto ${faceCount} twarzy. Porównanie odbywa się po stronie serwera.`}</p>}
    {images.filter(source => /\.(png|jpe?g|webp|gif)$/i.test(source)).slice(0, 2).map(source => <img className="evidenceImage" key={source} src={`/api/media?path=${encodeURIComponent(source)}`} alt={`Obraz z materiału: ${feature.name}`} />)}
    {short(feature.value, 130) !== short(feature.value, 2000) && <button className="textButton" onClick={() => setExpanded(!expanded)}>{expanded ? 'Zwiń' : 'Pokaż więcej'}</button>}
  </>
}

const anatomyDescriptions = {
  text: 'Treść, tytuły i słowa powtarzane między materiałami.',
  visual: 'Zrzuty i obrazy mogą zdradzić wspólne zasoby.',
  infra: 'Domeny, konta i identyfikatory wskazują wspólnego operatora.',
  template: 'Układ strony i elementy formularza ujawniają ten sam szablon.',
  person: 'Wizerunki z różnych materiałów można porównać ze sobą. Nazwiska z tekstu są osobnym śladem.',
}

function MaterialAnatomy({ item, demo }: { item: ItemDetail; demo: boolean }) {
  const [active, setActive] = useState(0)
  const image = primaryImage(item)
  useEffect(() => {
    if (!demo || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const timer = window.setInterval(() => setActive(value => (value + 1) % groups.length), 3500)
    return () => window.clearInterval(timer)
  }, [demo])
  const group = groups[active]
  const features = item.features.filter(feature => feature.group === group)
  return <Card className={anatomyStyles.anatomy}><div className={anatomyStyles.anatomyHeader}><div><span className="demoBadge">Anatomia materiału</span><h2>{item.id}</h2><p>Kolejne grupy pokazują, po czym materiał może zostać połączony z innymi.</p></div><CampaignChip campaign={item.campaign} /></div><div className={anatomyStyles.anatomyLayout}><div className={`${anatomyStyles.anatomyPreview} group-${group}`}>{image ? <img src={`/api/media?path=${encodeURIComponent(image)}`} alt={`Zrzut analizowanego materiału ${item.id}`} /> : <div className={anatomyStyles.anatomyPlaceholder}><span className={anatomyStyles.placeholderMark}>m</span><strong>{item.id}</strong><span>Brak zrzutu w tym materiale</span></div>}<div className={anatomyStyles.previewLabel}>{image ? 'Zrzut z materiału' : 'Analiza zapisanych danych'} <span>{active + 1} / {groups.length}</span></div></div><div className={anatomyStyles.anatomyEvidence}><div className={anatomyStyles.segmentTabs} role="tablist" aria-label="Grupy śladów">{groups.map((value, index) => <button role="tab" aria-selected={index === active} className={index === active ? `${anatomyStyles.selectedSegment} group-${value}` : ''} key={value} onClick={() => setActive(index)}>{String(index + 1).padStart(2, '0')} <span>{groupNames[value]}</span></button>)}</div><div role="tabpanel" className={anatomyStyles.segmentPanel} key={group}><GroupChip group={group} /><h3>{groupNames[group]}</h3><p>{anatomyDescriptions[group]}</p>{features.filter(feature => feature.available).slice(0, 3).map(feature => <div className={anatomyStyles.segmentFeature} key={feature.name}><strong>{featureLabel(feature.name)}</strong><span>{feature.name === 'person.faces' ? faceMatches(feature.value).map(face => face.label).join(', ') : feature.name === 'person.face_vectors' ? `Wykryto ${Number((feature.value as { count?: number })?.count || 0)} twarzy` : short(feature.value, 115)}</span><small>{Math.round(feature.confidence * 100)}% pewności</small></div>)}{features.filter(feature => !feature.available).slice(0, 2).map(feature => <div className={`${anatomyStyles.segmentFeature} ${anatomyStyles.segmentMissing}`} key={feature.name}><strong>{featureLabel(feature.name)}</strong><span>Brak danych: {short(feature.source, 115)}</span></div>)}{features.length === 0 && <p>Ten materiał nie zawiera cech z tej grupy.</p>}{group === 'person' && <p className={anatomyStyles.privacyNote}>Wynik porównania twarzy może być przesłanką połączenia materiałów. Pokazujemy obraz źródłowy z materiału, bez osobnej galerii osób.</p>}</div></div></div></Card>
}

export function Material({ demo = false }: { demo?: boolean }) {
  const { '*': encodedId } = useParams()
  const { data: items = [] } = useItems()
  const requestedId = encodedId ? decodeURIComponent(encodedId) : ''
  const itemId = items.find(item => item.id === requestedId)?.id || items[0]?.id
  const { data: item } = useQuery({ queryKey: ['item', itemId], enabled: !!itemId, queryFn: () => request<ItemDetail>(`/items/${encodeURIComponent(itemId!)}`) })
  return <Section title="Ślady materiału" lead="Dostępne cechy i jawne braki, pogrupowane według źródła dowodu." action={item && <CampaignChip campaign={item.campaign} />}>
    <div className="filters"><label>Materiał<select value={itemId || ''} onChange={event => { location.href = `/items/${encodeURIComponent(event.target.value)}` }}>{items.map(row => <option key={row.id} value={row.id}>{row.id}</option>)}</select></label></div>
    {!item ? <Empty>Wybierz materiał ze zbioru.</Empty> : <><MaterialAnatomy item={item} demo={demo} /><div className="groupSections">{groups.map(group => <div key={group}><h2 className={`groupTitle group-${group}`}>{groupNames[group]} <span>{item.features.filter(feature => feature.group === group).length}</span></h2><div className="featuresGrid">{item.features.filter(feature => feature.group === group).map(feature => <Card key={feature.name} className={!feature.available ? 'missingFeature' : ''}><div className="featureHead"><GroupChip group={feature.group} /><span>{feature.available ? `${Math.round(feature.confidence * 100)}% pewności` : 'Brak'}</span></div><h3>{featureLabel(feature.name)}</h3><FeatureValue feature={feature} /><Confidence value={feature.confidence} /><small>{feature.source}</small>{feature.truncated && <small>Lista skrócona do 50 pozycji</small>}</Card>)}</div></div>)}</div></>}
  </Section>
}

export function Compare() {
  const { data: items = [] } = useItems()
  const [params, setParams] = useSearchParams()
  const a = items.find(item => item.id === params.get('a'))?.id || items[0]?.id || ''
  const b = items.find(item => item.id === params.get('b') && item.id !== a)?.id || items.find(item => item.id !== a)?.id || ''
  const { data, isFetching } = useQuery({ queryKey: ['compare', a, b], enabled: !!a && !!b && a !== b, queryFn: () => post<Comparison>('/compare', { a, b }) })
  const hasFaces = data?.evidence.some(row => row.feature === 'person.face_vectors' || row.feature === 'person.faces') || false
  const first = useQuery({ queryKey: ['item', a], enabled: hasFaces, queryFn: () => request<ItemDetail>(`/items/${encodeURIComponent(a)}`) })
  const second = useQuery({ queryKey: ['item', b], enabled: hasFaces, queryFn: () => request<ItemDetail>(`/items/${encodeURIComponent(b)}`) })
  const evidence = [...(data?.evidence || [])].sort((x, y) => y.weight * y.score - x.weight * x.score)
  const update = (key: string, value: string) => { const next = new URLSearchParams(params); next.set(key, value); setParams(next) }
  return <Section className="compareSection" title="Porównanie materiałów" lead="Zobacz, które ślady wzmacniają połączenie, które mu przeczą i czego brakuje.">
    <div className="compareSelectors"><label>Pierwszy materiał<select value={a} onChange={event => update('a', event.target.value)}>{items.map(item => <option key={item.id}>{item.id}</option>)}</select></label><span className="compareConnector">↔</span><label>Drugi materiał<select value={b} onChange={event => update('b', event.target.value)}>{items.map(item => <option key={item.id}>{item.id}</option>)}</select></label></div>
    {hasFaces && <ImagePair first={primaryImage(first.data)} second={primaryImage(second.data)} firstLabel={a} secondLabel={b} />}
    {a === b ? <Empty>Wybierz dwa różne materiały.</Empty> : <div className="compareLayout"><Card className="resultCard">{isFetching && <span className="muted">Liczenie wyniku…</span>}<EdgeDetails card={data?.card || null} /></Card><div><h2>Składniki wyniku</h2>{evidence.length ? <div className="evidenceList">{evidence.map((row, index) => <Card key={`${row.feature}-${index}`} className="evidenceRow"><div className="evidenceHead"><GroupChip group={row.group} /><strong>{featureLabel(row.feature)}</strong><b>{Math.round(row.weight * row.score * 100)}%</b></div><div className={`contribution group-${row.group}`}><span style={{ width: `${Math.min(100, row.weight * row.score * 100)}%`, animationDelay: `${index * 100}ms` }} /></div><div className="evidenceValues"><span>{short(row.left, 80)}</span><span>{short(row.right, 80)}</span></div><p>{row.note}</p><small>Waga {row.weight.toFixed(2)} · zgodność {row.score.toFixed(2)}</small></Card>)}</div> : <Empty>Brak przesłanek do porównania.</Empty>}</div></div>}
  </Section>
}

export function CriteriaView() {
  const [caseLinks, setCaseLinks] = useState(false)
  const { data } = useQuery({ queryKey: ['criteria', caseLinks], queryFn: () => request<Criteria>(`/criteria?case_links=${caseLinks}`) })
  return <Section title="Kryteria grupowania" lead="Sześć odpowiedzi na pytanie: co znaczy „ta sama kampania”?" action={<label className="switchLabel"><input type="checkbox" checked={caseLinks} onChange={event => setCaseLinks(event.target.checked)} /> Łącz po przypadku</label>}>
    <div className="criteriaGrid">{data?.criteria.map(criterion => <Card key={criterion.key} className={criterion.key === 'combined' ? 'featuredCriterion' : ''}><h2>{criterion.label}</h2><p>{criterion.question}</p><div className="criterionStats"><b>{criterion.campaigns}</b><span>kampanii</span><b>{criterion.grouped_items}</b><span>materiałów w grupach</span></div><details><summary>Cechy i wagi</summary><ul>{criterion.features.map(feature => <li key={feature.name}>{feature.label} <b>{feature.weight.toFixed(2)}</b></li>)}</ul></details></Card>)}</div>
    <Card className="insight"><strong>Co widać?</strong><p>Pojedyncze kryterium może wskazać mocny wspólny ślad, ale pomija inne źródła dowodów. Sama platforma może łączyć różne działania, dlatego wynik łączony sprawdza kilka grup cech.</p></Card>
    <div className="matrixWrap"><table className="matrix"><thead><tr><th>Materiał</th>{data?.criteria.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{data?.membership.map(row => <tr key={row['materiał']}><th><ItemLink id={row['materiał']} /></th>{data.criteria.map(c => <td key={c.key}><CampaignChip campaign={row[c.label] === String.fromCharCode(8212) ? null : row[c.label]} /></td>)}</tr>)}</tbody></table></div>
  </Section>
}

const GROUP_OF_REASON: [RegExp, Group][] = [[/twarz|osob|nazw/i, 'person'], [/tracker|domen|konto|adres|certyfik|ip |serwer|rejestr|przekierow|favicon|hosty|ścieżk/i, 'infra'], [/dom|css|skrypt|formularz|komentarz|szablon|plik[ió]w zasobów|metadane/i, 'template'], [/obraz|zrzut|wygląd|klatk|plik \(/i, 'visual'], [/tekst|narrac|kontakt|słowa|kwot|tytu|temat|ocr/i, 'text']]

function reasonGroup(reason: string): Group {
  return GROUP_OF_REASON.find(([pattern]) => pattern.test(reason))?.[1] ?? 'text'
}

function topReasons(card: Graph['links'][number]['card']): string[] {
  const reasons = (card as { reasons?: string[] }).reasons || []
  return reasons.slice(0, 3).map(reason => reason.split(':')[0].replace(/\s*\(wkład.*$/, ''))
}

function EdgeList({ graph, selection, onSelect }: { graph: Graph; selection: Selection; onSelect: (selection: Selection) => void }) {
  const campaignOf = new Map(graph.nodes.map(node => [node.id, node.singleton ? null : node.campaign]))
  const linked = graph.links.filter(link => link.linked || link.case).sort((x, y) => (campaignOf.get(x.a) || '~').localeCompare(campaignOf.get(y.a) || '~') || y.score - x.score)
  if (!linked.length) return <p className="muted">Brak połączeń powyżej progu.</p>
  return <div className="edgeList">{linked.map(link => {
    const active = selection?.type === 'edge' && selection.a === link.a && selection.b === link.b
    return <button key={edgeKey(link.a, link.b)} className={`edgeRow ${active ? 'activeEdge' : ''}`} onClick={() => onSelect({ type: 'edge', a: link.a, b: link.b })}>
      <span className="edgeNodes"><b>{shortId(link.a)}</b><i>↔</i><b>{shortId(link.b)}</b></span>
      <span className="edgeMeta">{link.case ? <span className="reasonChip caseChip">ten sam przypadek</span> : <>{campaignOf.get(link.a) && <span className="campaignChip">{campaignOf.get(link.a)}</span>}<strong>{Math.round(link.score * 100)}%</strong></>}</span>
      {!link.case && <span className="edgeReasons">{topReasons(link.card).map(reason => <span key={reason} className={`reasonChip group-${reasonGroup(reason)}`}>{reason}</span>)}</span>}
    </button>
  })}</div>
}

function SelectionDetails({ graph, selection }: { graph: Graph; selection: Selection }) {
  if (!selection) return <p className="muted">Kliknij węzeł albo linię, żeby zobaczyć, dlaczego materiały zostały połączone.</p>
  if (selection.type === 'node') {
    const node = graph.nodes.find(candidate => candidate.id === selection.id)
    const links = graph.links.filter(link => link.a === selection.id || link.b === selection.id).sort((x, y) => y.score - x.score)
    return <div className="edgeDetails"><h3>{shortId(selection.id)}</h3><p className="muted">{node?.singleton ? 'Pojedynczy wzorzec: żadne powiązanie nie przekroczyło progu.' : `Kampania ${node?.campaign}`}</p><ul>{links.slice(0, 6).map(link => <li key={edgeKey(link.a, link.b)}>{shortId(link.a === selection.id ? link.b : link.a)}: {Math.round(link.score * 100)}% {link.linked ? '(połączone)' : '(poniżej progu)'}</li>)}</ul><Link className="textButton" to={`/items/${encodeURIComponent(selection.id)}`}>Pokaż ślady materiału →</Link></div>
  }
  const link = graph.links.find(candidate => candidate.a === selection.a && candidate.b === selection.b)
  if (!link) return null
  if (link.case) return <div className="edgeDetails"><strong>Ten sam przypadek</strong><p>{(link.card as { summary: string }).summary}</p><p>{shortId(link.a)} i {shortId(link.b)}</p><p className="muted">To powiązanie wynika ze wspólnego zgłoszenia, a nie z wyniku podobieństwa.</p></div>
  return <EdgeDetails card={link.card as EdgeCard} />
}

export function MapView({ theme, heading = true }: { theme: string; heading?: boolean }) {
  const query = useQueryClient()
  const { data: state } = useStateData()
  const { data: graph } = useQuery({ queryKey: ['graph', state?.threshold, state?.method, state?.case_links], queryFn: () => request<Graph>('/graph?min_edge=0.1'), enabled: !!state })
  const [threshold, setThreshold] = useState(state?.threshold ?? 0.5)
  const [selection, setSelection] = useState<Selection>(null)
  const [showWeak, setShowWeak] = useState(false)
  const mutation = useMutation({ mutationFn: (body: object) => post<AppState>('/settings', body), onSuccess: () => query.invalidateQueries() })
  useEffect(() => { if (state) setThreshold(state.threshold) }, [state?.threshold])
  const body = <>
    <div className="mapControls card"><label>Próg połączenia <strong>{threshold.toFixed(2)}</strong><input type="range" min="0.2" max="0.95" step="0.01" value={threshold} onChange={event => setThreshold(Number(event.target.value))} onPointerUp={() => mutation.mutate({ threshold })} onKeyUp={() => mutation.mutate({ threshold })} /></label><label>Metoda<select value={state?.method || 'components'} onChange={event => mutation.mutate({ method: event.target.value })}><option value="components">Składowe grafu</option><option value="average">Średnie wiązanie</option></select></label><label className="switchLabel"><input type="checkbox" checked={state?.case_links || false} onChange={event => mutation.mutate({ case_links: event.target.checked })} /> Łącz po przypadku</label><label className="switchLabel"><input type="checkbox" checked={showWeak} onChange={event => setShowWeak(event.target.checked)} /> Pokaż słabsze powiązania</label></div>
    <div className="mapLayout"><div className="card graphCard">{graph ? <CampaignGraph graph={graph} showWeak={showWeak} selection={selection} onSelect={setSelection} theme={theme} /> : <div className="graphCanvas graphLoading">Ładowanie mapy…</div>}<div className="graphLegend"><span><i className="swatch" /> ramka = kampania</span><span><i className="swatch grey" /> pojedynczy wzorzec</span><span><i className="solidLine" /> połączone, grubość = wynik</span><span><i className="dottedLine" /> ten sam przypadek</span><span><i className="dashedLine" /> słabsze, poniżej progu</span></div></div>
      <div className="mapSide"><div className="card mapDetails"><h2>Wybrane powiązanie</h2><SelectionDetails graph={graph || { nodes: [], links: [], threshold: 0 }} selection={selection} /></div><div className="card mapDetails"><h2>Wszystkie powiązania</h2><p className="muted">Każda linia na mapie z głównymi przesłankami.</p>{graph && <EdgeList graph={graph} selection={selection} onSelect={setSelection} />}</div></div></div>
  </>
  if (!heading) return body
  return <Section title="Mapa kampanii" lead="Ramki to kampanie, węzły to materiały. Grubość linii pokazuje siłę połączenia, a każdą linię można rozwinąć i sprawdzić jej uzasadnienie.">{body}</Section>
}

export function CampaignsView() {
  const { data: campaigns = [] } = useCampaigns()
  return <Section title="Kampanie" lead="Karty pokazują wspólne ślady, członków i miejsca, w których brakuje danych." action={<div className="exportLinks"><a href="/api/export/json">Raport JSON</a><a href="/api/export/csv">Raport CSV</a><a href="/api/export/html">Raport HTML</a><a href="/api/export/dataset-csv">Zbiór cech CSV</a><a href="/api/export/dataset-json">Zbiór cech JSON</a></div>}>
    {campaigns.length ? <div className="campaignGrid">{campaigns.map(campaign => <Card key={campaign.id} className="campaignCard"><div className="campaignTitle"><CampaignChip campaign={campaign.id} /><span>{campaign.size} materiałów</span></div><h2>{campaign.id}</h2><h3>Materiały</h3><div className="memberList">{campaign.members.map(id => <ItemLink key={id} id={id} />)}</div><h3>Co je łączy</h3>{campaign.links.length ? <ul>{campaign.links.slice(0, 5).map(link => <li key={link.feature}><GroupChip group={link.group} /> {link.label} <span className="muted">{link.edges} połączeń</span></li>)}</ul> : <p>Brak wspólnych przesłanek.</p>}<details><summary>Wspólne ślady i braki</summary>{Object.entries(campaign.shared_traits).map(([name, values]) => <p key={name}><b>{name}</b>: {values.map(([value, count]) => `${short(value, 50)} (${count})`).join(', ')}</p>)}{campaign.missing.map(missing => <p key={missing.feature}>{missing.feature}: brak w {missing.items.length} materiałach</p>)}</details><details><summary>Połączenia z uzasadnieniem</summary>{campaign.edges.map(edge => <div key={`${edge.a}-${edge.b}`} className="campaignEdge"><EdgeDetails card={edge} /></div>)}</details></Card>)}</div> : <Empty>Nie znaleziono kampanii. Pojedyncze materiały są widoczne w zbiorze.</Empty>}
  </Section>
}

function ExtractedFeatures({ features }: { features: Feature[] }) {
  const available = features.filter(feature => feature.available)
  return <section className="extracted"><h3>Wyodrębnione cechy <span className="muted">({available.length} z {features.length})</span></h3><div className="extractedGroups">{groups.map(group => {
    const rows = features.filter(feature => feature.group === group)
    if (!rows.length) return null
    return <div key={group} className="extractedGroup"><GroupChip group={group} /><ul>{rows.map(feature => <li key={feature.name} className={feature.available ? '' : 'missingValue'}><b>{featureLabel(feature.name)}</b> {feature.available ? <span>{feature.name === 'person.faces' ? faceMatches(feature.value).map(face => face.label).join(', ') : feature.name === 'person.face_vectors' ? `${Number((feature.value as { count?: number })?.count || 0)} twarzy` : short(feature.value, 70)}</span> : <span>brak: {short(feature.source, 70)}</span>}</li>)}</ul></div>
  })}</div></section>
}

export function NewMaterial() {
  const query = useQueryClient()
  const navigate = useNavigate()
  const [files, setFiles] = useState<File[]>([])
  const [url, setUrl] = useState('')
  const [tab, setTab] = useState<'upload' | 'adlib'>('upload')
  const [terms, setTerms] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [phase, setPhase] = useState(0)
  const [params] = useSearchParams()
  const demoSample = params.get('demo_sample')
  const demoItem = params.get('demo_item')
  const { data: appState } = useStateData()
  const lastSample = useRef('')
  const analyze = useMutation({ mutationFn: async (form: FormData) => { setPhase(0); const result = await request<Analysis>('/analyze', { method: 'POST', body: form }); setPhase(4); return result }, onSuccess: setAnalysis })
  useEffect(() => {
    if (!analyze.isPending) return
    const timer = window.setInterval(() => setPhase(value => Math.min(3, value + 1)), 550)
    return () => window.clearInterval(timer)
  }, [analyze.isPending])
  useEffect(() => {
    const key = demoItem ? `item:${demoItem}` : demoSample ? `sample:${demoSample}` : ''
    if (!key || lastSample.current === key) return
    lastSample.current = key
    const form = new FormData()
    if (demoItem) form.append('existing_id', demoItem)
    else if (demoSample === 'known' || demoSample === 'unknown') form.append('files', new File([demoSamples[demoSample]], `${demoSample}.html`, { type: 'text/html' }))
    else return
    setAnalysis(null)
    analyze.mutate(form)
  }, [demoSample, demoItem])
  const submit = () => { const form = new FormData(); files.forEach(file => form.append('files', file)); if (url) form.append('url', url); setAnalysis(null); analyze.mutate(form) }
  const add = useMutation({ mutationFn: (id: string) => post('/items', { upload_id: id }), onSuccess: () => { query.invalidateQueries(); navigate('/') } })
  const bestItemId = analysis?.similar[0]?.item
  const bestItem = useQuery({ queryKey: ['item', bestItemId], enabled: !!bestItemId, queryFn: () => request<ItemDetail>(`/items/${encodeURIComponent(bestItemId!)}`) })
  const adlib = useMutation({ mutationFn: () => post<{ results: { item: { id: string }; card: Analysis['card'] }[]; notice: string | null }>('/adlib/search', { terms, countries: ['PL'], max_pages: 1 }) })
  return <Section title="Nowy materiał" lead="Przeanalizuj materiał przed dodaniem go do zbioru. Możesz podać plik, ZIP lub adres URL.">
    <div className="tabs"><button className={tab === 'upload' ? 'activeTab' : ''} onClick={() => setTab('upload')}>Plik lub adres</button><button className={tab === 'adlib' ? 'activeTab' : ''} onClick={() => setTab('adlib')}>Biblioteka reklam</button></div>
    {tab === 'upload' ? <div className="newLayout"><Card><form onSubmit={event => { event.preventDefault(); submit() }}><label className="dropzone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); setFiles(Array.from(event.dataTransfer.files)) }}><strong>Przeciągnij pliki tutaj</strong><span>lub wybierz z dysku</span><input type="file" multiple onChange={event => setFiles(Array.from(event.currentTarget.files || []))} /></label>{files.length > 0 && <p>{files.map(file => file.name).join(', ')}</p>}<label>Adres URL<input type="url" placeholder="https://przyklad.test" value={url} onChange={event => setUrl(event.target.value)} /></label><button className="primaryButton" disabled={(!files.length && !url) || analyze.isPending}>Analizuj materiał</button></form>{analyze.isPending && <div className="progressSteps">{['Wczytywanie', 'Wyciąganie cech', 'Porównanie ze zbiorem', 'Przypisanie'].map((label, index) => <span className={index <= phase ? 'currentPhase' : ''} key={label}>{label}</span>)}</div>}{analyze.error && <p className="errorMessage">{analyze.error.message}</p>}</Card><div>{analysis ? <Card className="analysisCard"><span className="demoBadge">Wynik analizy</span><h2>{analysis.card.verdict}</h2><Score value={analysis.card.score} /><p>{analysis.card.basis}</p>{analysis.card.runner_up && <p>Drugie dopasowanie: {analysis.card.runner_up}</p>}{analysis.card.reasons.map((reason, index) => <p key={index}>{reason}</p>)}<ExtractedFeatures features={analysis.features} /><ImagePair first={analysis.item.media?.[0] || null} second={primaryImage(bestItem.data)} firstLabel="Nowy materiał" secondLabel={bestItemId || 'Najbliższy materiał'} />{analysis.missing.length > 0 && <details><summary>Brakujące cechy ({analysis.missing.length})</summary>{analysis.missing.map(row => <p key={row.feature}>{row.feature}: {row.reason}</p>)}</details>}{analysis.best_edge_card && <EdgeDetails card={analysis.best_edge_card} />}<h3>Najbardziej podobne</h3>{analysis.similar.slice(0, 5).map(similar => <p key={similar.item}><ItemLink id={similar.item} /> · {Math.round(similar.score * 100)}% · {similar.campaign || 'bez kampanii'}</p>)}{!analysis.existing && <button className="primaryButton" disabled={add.isPending} onClick={() => add.mutate(analysis.item.id)}>Dodaj do zbioru</button>}{analysis.existing && <p className="muted">To materiał już obecny w zbiorze, porównany z resztą tak, jakby był nowy.</p>}{add.error && <p className="errorMessage">{add.error.message}</p>}</Card> : <Empty>Wynik przypisania pojawi się tutaj. Materiał nie zostanie dodany bez Twojej decyzji.</Empty>}</div></div> : <Card className="adlibCard"><h2>Biblioteka reklam Meta</h2><p className="muted">Wyszukaj reklamy po frazie. Każda znaleziona reklama zostanie porównana ze zbiorem i przypisana do kampanii albo oznaczona jako nowy wzorzec.</p><form onSubmit={event => { event.preventDefault(); adlib.mutate() }}><label>Szukana fraza<input value={terms} onChange={event => setTerms(event.target.value)} minLength={2} maxLength={120} disabled={appState?.adlib_enabled === false} /></label><button className="primaryButton" disabled={adlib.isPending || terms.length < 2 || appState?.adlib_enabled === false}>Szukaj reklam</button></form>{appState?.adlib_enabled === false && <div className="infoNote"><strong>Wyszukiwanie jest wyłączone.</strong><span>Wymaga tokenu dostępu do Meta Ad Library, ustawionego na serwerze w zmiennej <code>META_AD_LIBRARY_TOKEN</code>, albo trybu weryfikacji <code>MIMIC_ADLIB_FIXTURE=1</code>. Bez tego pozostałe funkcje działają bez zmian.</span></div>}{appState?.adlib_mode === 'fixture' && <div className="infoNote"><strong>Tryb weryfikacji.</strong><span>Wyniki pochodzą z wbudowanego zestawu syntetycznych reklam, bez tokenu i bez sieci. Wyszukaj na przykład „inwestycje”, „stawy” albo „nagroda”.</span></div>}{adlib.data?.notice && <p className="muted">{adlib.data.notice}</p>}{adlib.data?.results.map(row => <p key={row.item.id}>{row.item.id}: {row.card.verdict}</p>)}{adlib.error && <p className="errorMessage">{adlib.error.message}</p>}</Card>}
  </Section>
}

function TiltTile({ onError }: { onError: () => void }) {
  const tile = useRef<HTMLDivElement>(null)
  const move = (event: React.PointerEvent<HTMLDivElement>) => {
    const box = tile.current?.getBoundingClientRect()
    if (!box || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const x = (event.clientX - box.left) / box.width - 0.5
    const y = (event.clientY - box.top) / box.height - 0.5
    tile.current?.style.setProperty('--ry', `${(x * 9).toFixed(2)}deg`)
    tile.current?.style.setProperty('--rx', `${(-y * 7).toFixed(2)}deg`)
    tile.current?.style.setProperty('--gx', `${((x + 0.5) * 100).toFixed(0)}%`)
  }
  const leave = () => { tile.current?.style.setProperty('--ry', '0deg'); tile.current?.style.setProperty('--rx', '0deg'); tile.current?.style.setProperty('--gx', '50%') }
  return <div className="heroMedia" ref={tile} onPointerMove={move} onPointerLeave={leave}><video src="/film.mp4" autoPlay muted loop playsInline controls preload="metadata" aria-label="Film pokazujący działanie mimic" onError={onError} /></div>
}

export function Home({ theme }: { theme: string }) {
  const { data: state } = useStateData()
  const location = useLocation()
  const [videoOk, setVideoOk] = useState(true)
  useEffect(() => {
    if (location.hash === '#mapa') window.setTimeout(() => document.getElementById('mapa')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    else window.scrollTo({ top: 0 })
  }, [location.hash, location.key])
  const stats = state?.stats
  return <div className="home">
    <section className="hero">
      <div className="heroText">
        <h1>Więcej zaufania do tego, co widzisz.</h1>
        <p>Mimic łączy podejrzane reklamy i strony w kampanie. Każde połączenie ma uzasadnienie: ten sam tracker, ten sam szablon, ta sama osoba. Nowy materiał trafia do istniejącej kampanii albo zostaje nowym wzorcem.</p>
        <div className="heroActions"><a className="primaryButton" href="#mapa" onClick={event => { event.preventDefault(); document.getElementById('mapa')?.scrollIntoView({ behavior: 'smooth' }) }}>Zobacz mapę kampanii</a><Link className="ghostButton" to="/new">Przeanalizuj nowy materiał</Link></div>
        <dl className="heroStats"><div><dt>{stats?.items ?? '–'}</dt><dd>materiałów</dd></div><div><dt>{stats?.campaigns ?? '–'}</dt><dd>kampanii</dd></div><div><dt>{stats?.singletons ?? '–'}</dt><dd>nowych wzorców</dd></div></dl>
        {state?.is_demo && <span className="demoBadge">Dane demonstracyjne</span>}
      </div>
      {videoOk && <TiltTile onError={() => setVideoOk(false)} />}
    </section>
    <section id="mapa" className="homeSection">
      <div className="homeSectionHead"><h2>Mapa kampanii</h2><p>Ramki to kampanie, węzły to materiały. Grubość linii pokazuje siłę połączenia, a każdą linię można rozwinąć i sprawdzić jej uzasadnienie.</p></div>
      <MapView theme={theme} heading={false} />
    </section>
    <section className="homeSection">
      <div className="homeSectionHead"><h2>Jak to działa</h2><p>Trzy kroki, z których każdy da się rozłożyć na czynniki pierwsze.</p></div>
      <div className="stepsGrid">
        <Link to="/items" className="card stepCard"><span className="stepNumber">1</span><h3>Ślady</h3><p>Z każdego materiału wyciągamy pięć rodzajów śladów: tekst, obraz, infrastrukturę, szablon i osoby. Brak danych zostaje jawnym brakiem, a nie zerem.</p><div className="chips">{groups.map(group => <GroupChip key={group} group={group} />)}</div></Link>
        <Link to="/compare" className="card stepCard"><span className="stepNumber">2</span><h3>Porównanie</h3><p>Podobieństwo składa się z przesłanek o znanych wagach. Dla każdej pary widać, co je wzmacnia, co przeczy i co zmieniłoby wynik.</p><div className="miniBars"><i style={{ width: '82%' }} /><i style={{ width: '56%' }} /><i style={{ width: '31%' }} /></div></Link>
        <Link to="/criteria" className="card stepCard"><span className="stepNumber">3</span><h3>Kampanie</h3><p>Połączenie wymaga twardego śladu albo dowodów z niezależnych źródeł. Sześć kryteriów pokazuje, po czym można dzielić na kampanie i czego żadne z nich samo nie widzi.</p></Link>
      </div>
    </section>
  </div>
}
