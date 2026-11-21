import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import brand from './brand.json'
import anatomyStyles from './Anatomy.module.css'
import { demoSamples } from './demo/script'
import { faceMatches, featureLabel, post, request, short, groups, groupNames } from './api'
import type { Analysis, AppState, Campaign, Comparison, Criteria, EdgeCard, Feature, Graph, ItemDetail, ItemRow } from './api'
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
  return <div className="imagePair">{[[first, firstLabel], [second, secondLabel]].map(([path, label]) => <div key={label}><strong>{label}</strong>{path ? <img src={`/api/media?path=${encodeURIComponent(path)}`} alt={`Obraz źródłowy: ${label}`} /> : <p>Brak zrzutu</p>}</div>)}</div>
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
  return <Section title="Porównanie materiałów" lead="Zobacz, które ślady wzmacniają połączenie, które mu przeczą i czego brakuje.">
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

export function MapView({ theme }: { theme: string }) {
  const query = useQueryClient()
  const { data: state } = useStateData()
  const { data: graph } = useQuery({ queryKey: ['graph', state?.threshold, state?.method, state?.case_links], queryFn: () => request<Graph>('/graph?min_edge=0.1'), enabled: !!state })
  const [threshold, setThreshold] = useState(state?.threshold ?? 0.5)
  const [selected, setSelected] = useState<Graph['links'][number] | null>(null)
  const canvas = useRef<HTMLDivElement>(null)
  const cy = useRef<cytoscape.Core | null>(null)
  const positions = useRef<Record<string, cytoscape.Position>>({})
  const mutation = useMutation({ mutationFn: (body: object) => post<AppState>('/settings', body), onSuccess: () => query.invalidateQueries() })
  useEffect(() => { if (state) setThreshold(state.threshold) }, [state?.threshold])
  useEffect(() => {
    if (!canvas.current || !graph) return
    const palette = brand.campaign_palette
    const campaignIds = [...new Set(graph.nodes.map(node => node.campaign).filter(Boolean))]
    const elements = [
      ...graph.nodes.map(node => ({ data: { id: node.id, label: node.id, color: node.singleton ? brand.singleton_color : palette[campaignIds.indexOf(node.campaign) % palette.length] }, ...(positions.current[node.id] ? { position: positions.current[node.id] } : {}) })),
      ...graph.links.map((link, index) => ({ data: { id: `edge-${index}`, source: link.a, target: link.b, score: link.score, linked: link.linked, case: !!link.case, card: link.card } })),
    ]
    const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text').trim()
    const backgroundColor = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
    cy.current = cytoscape({ container: canvas.current, elements, style: [
      { selector: 'node', style: { 'background-color': 'data(color)', label: 'data(label)', color: textColor, 'font-size': 12, 'font-family': 'Geist', 'text-valign': 'bottom', 'text-margin-y': 8, width: 22, height: 22, 'border-width': 3, 'border-color': backgroundColor } },
      { selector: 'edge', style: { width: 2, 'line-color': '#b9b9c2', 'curve-style': 'bezier', 'line-style': 'dashed', opacity: 0.6 } },
      { selector: 'edge[?linked]', style: { width: 4, 'line-color': '#5546ff', 'line-style': 'solid', opacity: 0.85 } },
      { selector: 'edge[?case]', style: { width: 3, 'line-color': '#a855f7', 'line-style': 'dotted' } },
    ], layout: { name: 'cose', animate: !matchMedia('(prefers-reduced-motion: reduce)').matches, animationDuration: 500 }, wheelSensitivity: 0.15 })
    cy.current.on('tap', 'edge', event => {
      const edge = event.target.data()
      setSelected({ a: edge.source, b: edge.target, score: edge.score, linked: edge.linked, case: edge.case, card: edge.card })
    })
    return () => {
      cy.current?.nodes().forEach(node => { positions.current[node.id()] = node.position() })
      cy.current?.destroy()
      cy.current = null
    }
  }, [graph, theme])
  return <Section title="Mapa kampanii" lead="Materiały są węzłami. Grubość i rodzaj linii pokazują siłę oraz podstawę połączenia.">
    <div className="mapControls card"><label>Próg połączenia <strong>{threshold.toFixed(2)}</strong><input type="range" min="0" max="1" step="0.01" value={threshold} onChange={event => setThreshold(Number(event.target.value))} onPointerUp={() => mutation.mutate({ threshold })} onKeyUp={() => mutation.mutate({ threshold })} /></label><label>Metoda<select value={state?.method || 'components'} onChange={event => mutation.mutate({ method: event.target.value })}><option value="components">Składowe grafu</option><option value="average">Średnie wiązanie</option></select></label><label className="switchLabel"><input type="checkbox" checked={state?.case_links || false} onChange={event => mutation.mutate({ case_links: event.target.checked })} /> Łącz po przypadku</label></div>
    <div className="mapLayout"><Card className="graphCard"><div ref={canvas} className="graphCanvas" role="img" aria-label="Graf powiązań materiałów" /><div className="graphLegend"><span><i className="solidLine" /> połączone</span><span><i className="dashedLine" /> poniżej progu</span><span><i className="dottedLine" /> ten sam przypadek</span></div></Card><Card className="mapDetails"><h2>Uzasadnienie krawędzi</h2>{selected?.case ? <div className="edgeDetails"><strong>Ten sam przypadek</strong><p>{selected.card.summary}</p><p>{selected.a} i {selected.b}</p><p className="muted">To powiązanie wynika ze wspólnego zgłoszenia, a nie z wyniku podobieństwa.</p></div> : selected ? <EdgeDetails card={selected.card as EdgeCard} /> : <p>Kliknij linię między dwoma materiałami.</p>}</Card></div>
  </Section>
}

export function CampaignsView() {
  const { data: campaigns = [] } = useCampaigns()
  return <Section title="Kampanie" lead="Karty pokazują wspólne ślady, członków i miejsca, w których brakuje danych." action={<div className="exportLinks"><a href="/api/export/json">JSON</a><a href="/api/export/csv">CSV</a><a href="/api/export/html">HTML</a></div>}>
    {campaigns.length ? <div className="campaignGrid">{campaigns.map(campaign => <Card key={campaign.id} className="campaignCard"><div className="campaignTitle"><CampaignChip campaign={campaign.id} /><span>{campaign.size} materiałów</span></div><h2>{campaign.id}</h2><h3>Materiały</h3><div className="memberList">{campaign.members.map(id => <ItemLink key={id} id={id} />)}</div><h3>Co je łączy</h3>{campaign.links.length ? <ul>{campaign.links.slice(0, 5).map(link => <li key={link.feature}><GroupChip group={link.group} /> {link.label} <span className="muted">{link.edges} połączeń</span></li>)}</ul> : <p>Brak wspólnych przesłanek.</p>}<details><summary>Wspólne ślady i braki</summary>{Object.entries(campaign.shared_traits).map(([name, values]) => <p key={name}><b>{name}</b>: {values.map(([value, count]) => `${short(value, 50)} (${count})`).join(', ')}</p>)}{campaign.missing.map(missing => <p key={missing.feature}>{missing.feature}: brak w {missing.items.length} materiałach</p>)}</details><details><summary>Połączenia z uzasadnieniem</summary>{campaign.edges.map(edge => <div key={`${edge.a}-${edge.b}`} className="campaignEdge"><EdgeDetails card={edge} /></div>)}</details></Card>)}</div> : <Empty>Nie znaleziono kampanii. Pojedyncze materiały są widoczne w zbiorze.</Empty>}
  </Section>
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
  const lastSample = useRef('')
  const analyze = useMutation({ mutationFn: async (form: FormData) => { setPhase(0); const result = await request<Analysis>('/analyze', { method: 'POST', body: form }); setPhase(4); return result }, onSuccess: setAnalysis })
  useEffect(() => {
    if (!analyze.isPending) return
    const timer = window.setInterval(() => setPhase(value => Math.min(3, value + 1)), 550)
    return () => window.clearInterval(timer)
  }, [analyze.isPending])
  useEffect(() => {
    if (demoSample !== 'known' && demoSample !== 'unknown') return
    if (lastSample.current === demoSample) return
    lastSample.current = demoSample
    const form = new FormData()
    form.append('files', new File([demoSamples[demoSample]], `${demoSample}.html`, { type: 'text/html' }))
    setAnalysis(null)
    analyze.mutate(form)
  }, [demoSample])
  const submit = () => { const form = new FormData(); files.forEach(file => form.append('files', file)); if (url) form.append('url', url); setAnalysis(null); analyze.mutate(form) }
  const add = useMutation({ mutationFn: (id: string) => post('/items', { upload_id: id }), onSuccess: () => { query.invalidateQueries(); navigate('/') } })
  const bestItemId = analysis?.similar[0]?.item
  const bestItem = useQuery({ queryKey: ['item', bestItemId], enabled: !!bestItemId, queryFn: () => request<ItemDetail>(`/items/${encodeURIComponent(bestItemId!)}`) })
  const adlib = useMutation({ mutationFn: () => post<{ results: { item: { id: string }; card: Analysis['card'] }[]; notice: string | null }>('/adlib/search', { terms, countries: ['PL'], max_pages: 1 }) })
  return <Section title="Nowy materiał" lead="Przeanalizuj materiał przed dodaniem go do zbioru. Możesz podać plik, ZIP lub adres URL.">
    <div className="tabs"><button className={tab === 'upload' ? 'activeTab' : ''} onClick={() => setTab('upload')}>Plik lub adres</button><button className={tab === 'adlib' ? 'activeTab' : ''} onClick={() => setTab('adlib')}>Biblioteka reklam</button></div>
    {tab === 'upload' ? <div className="newLayout"><Card><form onSubmit={event => { event.preventDefault(); submit() }}><label className="dropzone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); setFiles(Array.from(event.dataTransfer.files)) }}><strong>Przeciągnij pliki tutaj</strong><span>lub wybierz z dysku</span><input type="file" multiple onChange={event => setFiles(Array.from(event.currentTarget.files || []))} /></label>{files.length > 0 && <p>{files.map(file => file.name).join(', ')}</p>}<label>Adres URL<input type="url" placeholder="https://przyklad.test" value={url} onChange={event => setUrl(event.target.value)} /></label><button className="primaryButton" disabled={(!files.length && !url) || analyze.isPending}>Analizuj materiał</button></form>{analyze.isPending && <div className="progressSteps">{['Wczytywanie', 'Wyciąganie cech', 'Porównanie ze zbiorem', 'Przypisanie'].map((label, index) => <span className={index <= phase ? 'currentPhase' : ''} key={label}>{label}</span>)}</div>}{analyze.error && <p className="errorMessage">{analyze.error.message}</p>}</Card><div>{analysis ? <Card className="analysisCard"><span className="demoBadge">Wynik analizy</span><h2>{analysis.card.verdict}</h2><Score value={analysis.card.score} /><p>{analysis.card.basis}</p>{analysis.card.runner_up && <p>Drugie dopasowanie: {analysis.card.runner_up}</p>}{analysis.card.reasons.map((reason, index) => <p key={index}>{reason}</p>)}<ImagePair first={analysis.item.media?.[0] || null} second={primaryImage(bestItem.data)} firstLabel="Nowy materiał" secondLabel={bestItemId || 'Najbliższy materiał'} />{analysis.missing.length > 0 && <details><summary>Brakujące cechy ({analysis.missing.length})</summary>{analysis.missing.map(row => <p key={row.feature}>{row.feature}: {row.reason}</p>)}</details>}{analysis.best_edge_card && <EdgeDetails card={analysis.best_edge_card} />}<h3>Najbardziej podobne</h3>{analysis.similar.slice(0, 5).map(similar => <p key={similar.item}><ItemLink id={similar.item} /> · {Math.round(similar.score * 100)}% · {similar.campaign || 'bez kampanii'}</p>)}<button className="primaryButton" disabled={add.isPending} onClick={() => add.mutate(analysis.item.id)}>Dodaj do zbioru</button>{add.error && <p className="errorMessage">{add.error.message}</p>}</Card> : <Empty>Wynik przypisania pojawi się tutaj. Materiał nie zostanie dodany bez Twojej decyzji.</Empty>}</div></div> : <Card className="adlibCard"><form onSubmit={event => { event.preventDefault(); adlib.mutate() }}><label>Szukana fraza<input value={terms} onChange={event => setTerms(event.target.value)} minLength={2} maxLength={120} /></label><button className="primaryButton" disabled={adlib.isPending || terms.length < 2}>Szukaj reklam</button></form>{adlib.data?.notice && <p>{adlib.data.notice}</p>}{adlib.data?.results.map(row => <p key={row.item.id}>{row.item.id}: {row.card.verdict}</p>)}{adlib.error && <p className="errorMessage">{adlib.error.message}</p>}</Card>}
  </Section>
}
