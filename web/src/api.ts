export type Group = 'text' | 'visual' | 'infra' | 'template' | 'person'
export type Evidence = { feature: string; group: Group; weight: number; score: number; left: unknown; right: unknown; note: string }
export type EdgeCard = { a: string; b: string; score: number; linked: boolean; strength: string; basis: string; summary: string; reasons: string[]; contrary: string[]; missing: string[]; counterfactual: string; formula: string }
export type AppState = { is_demo: boolean; stats: { items: number; campaigns: number; singletons: number; insufficient: number }; threshold: number; method: 'components' | 'average'; case_links: boolean; formula: string; faces_enabled: boolean }
export type ItemRow = { id: string; case_id: string; kinds: string[]; campaign: string | null; singleton: boolean; available_features: number; missing_features: number }
export type Feature = { name: string; group: Group; value: unknown; confidence: number; source: string; available: boolean; truncated: boolean }
export type ItemDetail = { id: string; case_id: string; kinds: string[]; campaign: string | null; features: Feature[] }
export type Campaign = { id: string; size: number; members: string[]; cases: string[]; key_features: [string, number][]; links: { feature: string; group: Group; label: string; edges: number; strong: number; best: number; example: string }[]; shared_traits: Record<string, [string, number][]>; missing: { feature: string; group: Group; items: string[]; reason: string }[]; edges: EdgeCard[]; formula: string }
export type Graph = { nodes: { id: string; case: string; campaign: string | null; singleton: boolean; kinds: string[] }[]; links: { a: string; b: string; score: number; linked: boolean; case?: boolean; card: EdgeCard | { strength: string; summary: string; reasons: string[] } }[]; threshold: number }
export type Comparison = { score: number; linked: boolean; card: EdgeCard | null; evidence: Evidence[] }
export type Criteria = { criteria: { key: string; label: string; question: string; campaigns: number; grouped_items: number; singletons: number; features: { name: string; weight: number; label: string }[]; groups: string[][] }[]; membership: Record<string, string>[]; threshold: number }
export type Analysis = { item: { id: string; kinds: string[]; media: string[] }; assignment: { campaign_id: string | null; score: number }; card: { verdict: string; status: string; score: number; basis: string; runner_up: string | null; reasons: string[]; missing: string[] }; similar: { item: string; campaign: string | null; score: number; card: EdgeCard }[]; missing: { feature: string; group: Group; reason: string }[]; available: string[]; formula: string; best_edge_card: EdgeCard | null; is_new_pattern: boolean }

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?: string }
    throw new Error(body.error || `Błąd połączenia (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export function short(value: unknown, limit = 110): string {
  if (value == null) return '-'
  const cleaned = typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'minhash')) : value
  const text = typeof cleaned === 'string' ? cleaned : JSON.stringify(cleaned)
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

export const groupNames: Record<Group, string> = { text: 'Tekst', visual: 'Obraz', infra: 'Infrastruktura', template: 'Szablon', person: 'Osoba' }
export const groups = Object.keys(groupNames) as Group[]

export function featureLabel(name: string): string {
  return { 'person.face_vectors': 'Porównanie twarzy', 'person.faces': 'Rozpoznana osoba' }[name] || name
}

export function faceMatches(value: unknown): { label: string; score?: number }[] {
  if (Array.isArray(value)) return value.flatMap(entry => {
    if (typeof entry === 'string') return [{ label: entry }]
    if (!entry || typeof entry !== 'object') return []
    const row = entry as Record<string, unknown>
    const label = row.label || row.name || row.person || row.match_id
    const score = row.score || row.similarity || row.confidence
    return typeof label === 'string' ? [{ label, score: typeof score === 'number' ? score : undefined }] : []
  })
  if (value && typeof value === 'object') {
    const row = value as Record<string, unknown>
    return faceMatches(row.matches || row.faces)
  }
  return []
}
