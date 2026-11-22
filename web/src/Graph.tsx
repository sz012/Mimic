import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import brand from './brand.json'
import type { Graph } from './api'

export type Selection = { type: 'edge'; a: string; b: string } | { type: 'node'; id: string } | null

export function shortId(id: string): string {
  const parts = id.split('/')
  const unique = parts.filter((part, index) => index === 0 || part !== parts[index - 1])
  return unique.map(part => part.replace(/_/g, ' ')).join(' · ').replace(/(.{26}).+/, '$1…')
}

export function edgeKey(a: string, b: string): string {
  return `${a}|${b}`
}

export const GROUP_COLORS: Record<string, string> = { ...brand.group_colors, case: brand.colors.light.accent }

export const GROUP_LABELS: Record<string, string> = {
  infra: 'infrastruktura',
  template: 'szablon',
  text: 'tekst',
  visual: 'obraz',
  person: 'osoby',
}

type GraphNode = Graph['nodes'][number] & d3.SimulationNodeDatum
type GraphLink = Graph['links'][number] & { source: GraphNode | string; target: GraphNode | string; kind: 'linked' | 'case' | 'weak' }
type Packet = { link: GraphLink; offset: number }
type Handles = { fit: (only?: string[]) => void; nodes: d3.Selection<SVGGElement, GraphNode, SVGGElement, unknown>; links: d3.Selection<SVGLineElement, GraphLink, SVGGElement, unknown>; hulls: d3.Selection<SVGPathElement, [string, GraphNode[]], SVGGElement, unknown> }

type Props = { graph: Graph; showWeak: boolean; selection: Selection; onSelect: (selection: Selection) => void; theme: string }

const endpoint = (end: GraphNode | string) => end as GraphNode
const groupColor = (group?: string | null) => (group && GROUP_COLORS[group]) || 'var(--muted)'

function shortLabels(nodes: GraphNode[]): Record<string, string> {
  const labels: Record<string, string> = {}
  const byCase = d3.group(nodes, node => node.case || node.id.split('/')[0])
  byCase.forEach((members, caseId) => {
    const sorted = [...members].sort((x, y) => x.id.localeCompare(y.id))
    sorted.forEach((node, index) => {
      labels[node.id] = sorted.length === 1 ? caseId : `${caseId}/${index + 1}`
    })
  })
  return labels
}

export function CampaignGraph({ graph, showWeak, selection, onSelect, theme }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const positions = useRef(new Map<string, { x: number; y: number }>())
  const handles = useRef<Handles | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    const svgEl = svgRef.current
    if (!svgEl) return
    const svg = d3.select(svgEl)
    svg.selectAll('*').remove()
    const box = svgEl.getBoundingClientRect()
    const width = box.width || 800
    const height = box.height || 600
    const palette = brand.campaign_palette
    const campaignIds = [...new Set(graph.nodes.filter(node => !node.singleton && node.campaign).map(node => node.campaign as string))].sort()
    const colorOf = (node: GraphNode) => (node.singleton || !node.campaign ? brand.singleton_color : palette[campaignIds.indexOf(node.campaign) % palette.length])
    const saved = positions.current
    const nodes: GraphNode[] = graph.nodes.map(node => ({ ...node, ...(saved.get(node.id) ?? {}) }))
    const labels = shortLabels(nodes)
    const weakFloor = Math.max(0.2, graph.threshold - 0.25)
    const links: GraphLink[] = graph.links
      .filter(link => link.linked || link.case || (showWeak && link.score >= weakFloor))
      .map(link => ({ ...link, source: link.a, target: link.b, kind: link.case ? 'case' : link.linked ? 'linked' : 'weak' }))

    const root = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.25, 4]).on('zoom', event => root.attr('transform', event.transform))
    svg.call(zoom).on('dblclick.zoom', null)
    svg.on('click', event => { if (event.target === svgEl) onSelectRef.current(null) })
    const hullLayer = root.append('g')
    const linkLayer = root.append('g')
    const packetLayer = root.append('g')
    const nodeLayer = root.append('g')
    const tip = d3.select(tipRef.current)
    const showTip = (event: MouseEvent, lines: string[]) => {
      const [x, y] = d3.pointer(event, svgEl)
      tip.style('display', 'block').style('left', `${x + 14}px`).style('top', `${y + 14}px`).html('')
      tip.append('b').text(lines[0])
      lines.slice(1).filter(Boolean).forEach(line => tip.append('div').text(line))
    }
    const hideTip = () => tip.style('display', 'none')

    const linkSel = linkLayer
      .selectAll<SVGLineElement, GraphLink>('line.gLink')
      .data(links)
      .join('line')
      .attr('class', link => `gLink ${link.kind}`)
      .style('stroke', link => (link.kind === 'weak' ? null : groupColor(link.group)))
      .style('stroke-width', link => (link.kind === 'weak' ? 1 : link.kind === 'case' ? 1.6 : 1.2 + 2.6 * link.score))
    linkLayer
      .selectAll<SVGLineElement, GraphLink>('line.gHit')
      .data(links)
      .join('line')
      .attr('class', 'gHit')
      .on('mousemove', (event, link) => showTip(event, [`${shortId(link.a)} i ${shortId(link.b)}`, link.case ? 'ten sam przypadek' : `${Math.round(link.score * 100)}% · ${link.linked ? 'połączone' : 'poniżej progu'}`, link.group && link.group !== 'case' ? `główny ślad: ${GROUP_LABELS[link.group] ?? link.group}` : '']))
      .on('mouseleave', hideTip)
      .on('click', (event, link) => { event.stopPropagation(); onSelectRef.current({ type: 'edge', a: link.a, b: link.b }) })
    const hitSel = linkLayer.selectAll<SVGLineElement, GraphLink>('line.gHit')

    const packets: Packet[] = links.filter(link => link.kind === 'linked').map((link, index) => ({ link, offset: (index * 0.37) % 1 }))
    const packetSel = packetLayer
      .selectAll<SVGCircleElement, Packet>('circle')
      .data(packets)
      .join('circle')
      .attr('class', 'gPacket')
      .attr('r', 2.6)
      .style('fill', packet => groupColor(packet.link.group))

    const sim = d3
      .forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphLink>(links).id(node => node.id).distance(link => (link.kind === 'weak' ? 170 : 80)).strength(link => (link.kind === 'weak' ? 0.02 : 0.6)))
      .force('charge', d3.forceManyBody().strength(-320))
      .force('collide', d3.forceCollide(30))
      .force('x', d3.forceX(width / 2).strength(0.05))
      .force('y', d3.forceY(height / 2).strength(0.07))
    if (saved.size) sim.alpha(0.35)

    const nodeSel = nodeLayer
      .selectAll<SVGGElement, GraphNode>('g.gNode')
      .data(nodes, node => node.id)
      .join('g')
      .attr('class', 'gNode')
      .call(
        d3
          .drag<SVGGElement, GraphNode>()
          .on('start', (event, node) => { if (!event.active) sim.alphaTarget(0.2).restart(); node.fx = node.x; node.fy = node.y })
          .on('drag', (event, node) => { node.fx = event.x; node.fy = event.y })
          .on('end', (event, node) => { if (!event.active) sim.alphaTarget(0); node.fx = null; node.fy = null }),
      )
    nodeSel
      .append('circle')
      .attr('class', 'gCore')
      .attr('r', node => (node.singleton ? 8 : 10))
      .style('fill', colorOf)
      .on('mouseenter', (event, node) => {
        const near = new Set([node.id])
        links.forEach(link => {
          if (endpoint(link.source).id === node.id) near.add(endpoint(link.target).id)
          if (endpoint(link.target).id === node.id) near.add(endpoint(link.source).id)
        })
        nodeSel.classed('hoverDim', other => !near.has(other.id))
        linkSel.classed('hoverDim', link => endpoint(link.source).id !== node.id && endpoint(link.target).id !== node.id)
        showTip(event, [node.id, node.singleton ? 'pojedynczy wzorzec' : `kampania ${node.campaign}`, 'kliknij, aby zobaczyć powiązania'])
      })
      .on('mouseleave', () => { nodeSel.classed('hoverDim', false); linkSel.classed('hoverDim', false); hideTip() })
      .on('click', (event, node) => { event.stopPropagation(); onSelectRef.current({ type: 'node', id: node.id }) })
    nodeSel.append('text').attr('dy', -16).attr('text-anchor', 'middle').text(node => labels[node.id])

    const groups = d3.groups(nodes.filter(node => !node.singleton && node.campaign), node => node.campaign as string)
    const hullSel = hullLayer
      .selectAll<SVGPathElement, [string, GraphNode[]]>('path')
      .data(groups)
      .join('path')
      .attr('class', 'gHull')
      .style('fill', ([, members]) => colorOf(members[0]))
      .style('stroke', ([, members]) => colorOf(members[0]))
    const hullLabel = hullLayer
      .selectAll<SVGTextElement, [string, GraphNode[]]>('text')
      .data(groups)
      .join('text')
      .attr('class', 'gHullLabel')
      .attr('text-anchor', 'middle')
      .style('fill', ([, members]) => colorOf(members[0]))
      .text(([id, members]) => `${id} (${members.length})`)
    const hullPath = d3.line().curve(d3.curveCatmullRomClosed.alpha(0.6))

    const fit = (only?: string[]) => {
      const chosen = only && only.length ? nodes.filter(node => only.includes(node.id)) : nodes
      if (!chosen.length) return
      const bounds = svgEl.getBoundingClientRect()
      const w = bounds.width || width
      const h = bounds.height || height
      const xs = d3.extent(chosen, node => node.x ?? 0) as [number, number]
      const ys = d3.extent(chosen, node => node.y ?? 0) as [number, number]
      const scale = Math.min(1.8, 0.9 / Math.max((xs[1] - xs[0] + 140) / w, (ys[1] - ys[0] + 160) / h))
      const tx = w / 2 - scale * ((xs[0] + xs[1]) / 2)
      const ty = h / 2 - scale * ((ys[0] + ys[1]) / 2)
      svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
    }

    let settled = false
    sim.on('tick', () => {
      if (!settled && sim.alpha() < 0.04) { settled = true; fit() }
      const place = (sel: d3.Selection<SVGLineElement, GraphLink, SVGGElement, unknown>) =>
        sel.attr('x1', link => endpoint(link.source).x ?? 0).attr('y1', link => endpoint(link.source).y ?? 0).attr('x2', link => endpoint(link.target).x ?? 0).attr('y2', link => endpoint(link.target).y ?? 0)
      place(linkSel)
      place(hitSel)
      nodeSel.attr('transform', node => `translate(${node.x ?? 0},${node.y ?? 0})`)
      hullSel.attr('d', ([, members]) => {
        const points = members.flatMap(node => d3.range(8).map(k => [(node.x ?? 0) + 30 * Math.cos((k * Math.PI) / 4), (node.y ?? 0) + 30 * Math.sin((k * Math.PI) / 4)] as [number, number]))
        const hull = d3.polygonHull(points)
        return hull ? hullPath(hull) : null
      })
      hullLabel.attr('x', ([, members]) => d3.mean(members, node => node.x ?? 0) ?? 0).attr('y', ([, members]) => (d3.min(members, node => node.y ?? 0) ?? 0) - 38)
    })
    sim.on('end', () => fit())
    const lateFit = setTimeout(() => fit(), 2500)
    const observer = new ResizeObserver(() => fit())
    observer.observe(svgEl)

    let frame = 0
    const start = performance.now()
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const animate = (now: number) => {
      const t = (now - start) / 1000
      const at = (packet: Packet) => (t * (0.04 + 0.06 * packet.link.score) + packet.offset) % 1
      packetSel
        .attr('cx', packet => { const s = endpoint(packet.link.source); const e = endpoint(packet.link.target); return (s.x ?? 0) + ((e.x ?? 0) - (s.x ?? 0)) * at(packet) })
        .attr('cy', packet => { const s = endpoint(packet.link.source); const e = endpoint(packet.link.target); return (s.y ?? 0) + ((e.y ?? 0) - (s.y ?? 0)) * at(packet) })
      frame = requestAnimationFrame(animate)
    }
    if (!reduce) frame = requestAnimationFrame(animate)

    handles.current = { fit, nodes: nodeSel, links: linkSel, hulls: hullSel }
    return () => {
      nodes.forEach(node => { if (node.x !== undefined && node.y !== undefined) saved.set(node.id, { x: node.x, y: node.y }) })
      sim.stop()
      cancelAnimationFrame(frame)
      clearTimeout(lateFit)
      observer.disconnect()
      handles.current = null
    }
  }, [graph, theme, showWeak])

  useEffect(() => {
    const current = handles.current
    if (!current) return
    const { nodes, links, hulls } = current
    if (!selection) {
      nodes.classed('faded', false).classed('active', false)
      links.classed('faded', false).classed('active', false)
      hulls.classed('faded', false)
      return
    }
    const keep = new Set<string>()
    const isActive = (link: GraphLink) => {
      const a = endpoint(link.source).id
      const b = endpoint(link.target).id
      return selection.type === 'edge' ? (a === selection.a && b === selection.b) || (a === selection.b && b === selection.a) : a === selection.id || b === selection.id
    }
    links.each(link => { if (isActive(link)) { keep.add(endpoint(link.source).id); keep.add(endpoint(link.target).id) } })
    if (selection.type === 'node') keep.add(selection.id)
    links.classed('active', isActive).classed('faded', link => !isActive(link))
    nodes.classed('active', node => (selection.type === 'node' ? node.id === selection.id : keep.has(node.id))).classed('faded', node => !keep.has(node.id))
    hulls.classed('faded', ([, members]) => !members.some(node => keep.has(node.id)))
  }, [selection, graph, theme, showWeak])

  return (
    <div className="graphCanvas gGraph">
      <svg ref={svgRef} role="img" aria-label="Graf powiązań materiałów: kropki to materiały, obrysy to kampanie, kolor linii to główny rodzaj śladu, ruch pokazuje przepływ dowodów" />
      <div className="gTip" ref={tipRef} style={{ display: 'none' }} />
    </div>
  )
}
