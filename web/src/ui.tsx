import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { EdgeCard, Group } from './api'
import { groupNames, short } from './api'

export function Section({ title, lead, children, action, className = '' }: { title: string; lead?: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return <section className={`section ${className}`}><div className="sectionHead"><div><h1>{title}</h1>{lead && <p>{lead}</p>}</div>{action}</div>{children}</section>
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>
}

export function GroupChip({ group }: { group: Group }) {
  return <span className={`groupChip group-${group}`}>{groupNames[group]}</span>
}

export function CampaignChip({ campaign, singleton = false }: { campaign: string | null; singleton?: boolean }) {
  if (!campaign || singleton) return <span className="campaignChip mutedChip">Pojedynczy wzorzec</span>
  return <span className="campaignChip">{campaign}</span>
}

export function Confidence({ value }: { value: number }) {
  return <span className="confidence" title={`Pewność ${Math.round(value * 100)}%`}><span style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} /></span>
}

export function Empty({ children }: { children: ReactNode }) {
  return <Card className="empty">{children}</Card>
}

export function Score({ value }: { value: number }) {
  return <strong className="score">{Math.round(value * 100)}<small>%</small></strong>
}

function conciseSummary(summary: string, limit = 5): string {
  const [lead, rest] = summary.includes(': ') ? [summary.slice(0, summary.indexOf(': ') + 2), summary.slice(summary.indexOf(': ') + 2)] : ['', summary]
  const parts = rest.split('; ')
  return parts.length <= limit ? summary : `${lead}${parts.slice(0, limit).join('; ')} i ${parts.length - limit} więcej`
}

export function EdgeDetails({ card }: { card: EdgeCard | null }) {
  if (!card) return <Empty>Brak wspólnych przesłanek dla tej pary.</Empty>
  return <div className="edgeDetails">
    <div className="verdict"><span>{card.linked ? 'Połączone' : 'Nie połączone'}</span><Score value={card.score} /></div>
    <p>{conciseSummary(card.summary)}</p><p className="muted">{card.basis}</p>
    {card.reasons.length > 0 && <div><h3>Za połączeniem</h3><ul>{card.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>}
    {card.contrary.length > 0 && <div><h3>Przeciw</h3><ul>{card.contrary.map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>}
    {card.missing.length > 0 && <div><h3>Brak danych</h3><ul>{card.missing.map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>}
    <Card className="counterfactual"><strong>Co zmieniłoby wynik?</strong><p>{card.counterfactual}</p></Card>
    <details><summary>Wzór</summary><p>{card.formula}</p></details>
    {card.a && <p className="muted">{short(card.a)} i {short(card.b)}</p>}
  </div>
}

export function ItemLink({ id }: { id: string }) {
  return <Link to={`/items/${encodeURIComponent(id)}`}>{id}</Link>
}
