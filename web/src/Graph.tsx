import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
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

type Props = { graph: Graph; showWeak: boolean; selection: Selection; onSelect: (selection: Selection) => void; theme: string }

export function CampaignGraph({ graph, showWeak, selection, onSelect, theme }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const cy = useRef<cytoscape.Core | null>(null)
  const positions = useRef<Record<string, cytoscape.Position>>({})
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    if (!container.current) return
    const css = getComputedStyle(document.documentElement)
    const text = css.getPropertyValue('--text').trim() || '#0e0e11'
    const bg = css.getPropertyValue('--bg').trim() || '#ffffff'
    const muted = css.getPropertyValue('--muted').trim() || '#6b6b74'
    const primary = css.getPropertyValue('--primary').trim() || '#5546ff'
    const palette = brand.campaign_palette
    const campaigns = [...new Set(graph.nodes.filter(node => !node.singleton && node.campaign).map(node => node.campaign as string))]
    const colorOf = (campaign: string | null) => (campaign && campaigns.includes(campaign) ? palette[campaigns.indexOf(campaign) % palette.length] : brand.singleton_color)
    const sizeOf = (campaign: string) => graph.nodes.filter(node => node.campaign === campaign).length
    const visibleLinks = graph.links.filter(link => link.linked || link.case || (showWeak && link.score >= Math.max(0.2, graph.threshold - 0.25)))
    const elements: cytoscape.ElementDefinition[] = [
      ...campaigns.map(campaign => ({ data: { id: `campaign:${campaign}`, label: `${campaign} · ${sizeOf(campaign)} mat.`, color: colorOf(campaign), isCampaign: true } })),
      ...graph.nodes.map(node => ({
        data: { id: node.id, label: shortId(node.id), color: colorOf(node.singleton ? null : node.campaign), singleton: node.singleton, ...(node.singleton || !node.campaign ? {} : { parent: `campaign:${node.campaign}` }) },
        ...(positions.current[node.id] ? { position: positions.current[node.id] } : {}),
      })),
      ...visibleLinks.map(link => ({
        data: {
          id: edgeKey(link.a, link.b),
          source: link.a,
          target: link.b,
          score: link.score,
          linked: link.linked,
          case: !!link.case,
          label: link.case ? '' : link.linked ? `${Math.round(link.score * 100)}%` : '',
          width: link.case ? 2.5 : 1.5 + link.score * 5,
        },
      })),
    ]
    const instance = cytoscape({
      container: container.current,
      elements,
      wheelSensitivity: 0.2,
      minZoom: 0.3,
      maxZoom: 2.5,
      style: [
        { selector: 'node', style: { 'background-color': 'data(color)', width: 30, height: 30, 'border-width': 3, 'border-color': bg, label: 'data(label)', color: text, 'font-family': 'Geist, sans-serif', 'font-size': 13, 'font-weight': 500, 'text-valign': 'bottom', 'text-margin-y': 8, 'text-wrap': 'ellipsis', 'text-max-width': '130px', 'text-background-color': bg, 'text-background-opacity': 0.88, 'text-background-padding': '3px', 'text-background-shape': 'roundrectangle', 'min-zoomed-font-size': 7, 'overlay-opacity': 0 } },
        { selector: 'node[?singleton]', style: { 'background-color': brand.singleton_color } },
        { selector: ':parent', style: { shape: 'round-rectangle', 'background-color': 'data(color)', 'background-opacity': 0.09, 'border-width': 2, 'border-color': 'data(color)', 'border-opacity': 0.55, padding: '30px', label: 'data(label)', 'text-valign': 'top', 'text-halign': 'center', 'text-margin-y': -8, 'font-size': 14, 'font-weight': 600, color: text, 'text-background-opacity': 0, 'min-zoomed-font-size': 0 } },
        { selector: 'edge', style: { width: 'data(width)', 'line-color': muted, opacity: 0.4, 'curve-style': 'bezier', 'line-style': 'dashed', 'overlay-opacity': 0, label: 'data(label)', 'font-family': 'Geist, sans-serif', 'font-size': 12, 'font-weight': 600, color: text, 'text-background-color': bg, 'text-background-opacity': 0.92, 'text-background-padding': '3px', 'text-background-shape': 'roundrectangle', 'text-rotation': 'none', 'min-zoomed-font-size': 7 } },
        { selector: 'edge[?linked]', style: { 'line-color': primary, 'line-style': 'solid', opacity: 0.8 } },
        { selector: 'edge[?case]', style: { 'line-color': '#a855f7', 'line-style': 'dotted', opacity: 0.8, label: '' } },
        { selector: '.faded', style: { opacity: 0.12 } },
        { selector: 'edge.active', style: { opacity: 1, 'line-color': primary, 'z-index': 99 } },
        { selector: 'edge.active[?case]', style: { label: 'ten sam przypadek', 'line-color': '#a855f7' } },
        { selector: 'node.active', style: { 'border-color': primary, 'border-width': 4 } },
      ],
      layout: {
        name: 'cose',
        animate: !matchMedia('(prefers-reduced-motion: reduce)').matches,
        animationDuration: 600,
        randomize: Object.keys(positions.current).length === 0,
        fit: true,
        padding: 30,
        nodeDimensionsIncludeLabels: true,
        nodeRepulsion: () => 16000,
        idealEdgeLength: () => 105,
        nodeOverlap: 40,
        componentSpacing: 90,
        nestingFactor: 1.4,
        gravity: 0.5,
        numIter: 1800,
      } as cytoscape.LayoutOptions,
    })
    instance.on('tap', 'edge', event => { const data = event.target.data(); onSelectRef.current({ type: 'edge', a: data.source, b: data.target }) })
    instance.on('tap', 'node', event => { if (!event.target.data('isCampaign')) onSelectRef.current({ type: 'node', id: event.target.id() }) })
    instance.on('tap', event => { if (event.target === instance) onSelectRef.current(null) })
    instance.on('mouseover', 'edge', event => { container.current!.style.cursor = 'pointer'; event.target.addClass('active') })
    instance.on('mouseout', 'edge', event => { container.current!.style.cursor = 'default'; if (!event.target.data('selected')) event.target.removeClass('active') })
    instance.on('mouseover', 'node', () => { container.current!.style.cursor = 'pointer' })
    instance.on('mouseout', 'node', () => { container.current!.style.cursor = 'default' })
    cy.current = instance
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(container.current)
    return () => {
      observer.disconnect()
      instance.nodes().forEach(node => { if (!node.data('isCampaign')) positions.current[node.id()] = { ...node.position() } })
      instance.destroy()
      cy.current = null
    }
  }, [graph, theme, showWeak])

  useEffect(() => {
    const instance = cy.current
    if (!instance) return
    instance.elements().removeClass('active faded').forEach(element => { element.data('selected', false) })
    if (!selection) return
    instance.elements().addClass('faded')
    if (selection.type === 'edge') {
      const edge = instance.getElementById(edgeKey(selection.a, selection.b))
      edge.removeClass('faded').addClass('active').data('selected', true)
      edge.connectedNodes().removeClass('faded').addClass('active')
      edge.connectedNodes().ancestors().removeClass('faded')
    } else {
      const node = instance.getElementById(selection.id)
      const edges = node.connectedEdges()
      node.removeClass('faded').addClass('active')
      edges.removeClass('faded').addClass('active').forEach(edge => { edge.data('selected', true) })
      edges.connectedNodes().removeClass('faded')
      node.ancestors().removeClass('faded')
      edges.connectedNodes().ancestors().removeClass('faded')
    }
  }, [selection, graph, theme, showWeak])

  return <div ref={container} className="graphCanvas" role="img" aria-label="Graf powiązań materiałów: węzły to materiały, ramki to kampanie, linie to powiązania z uzasadnieniem" />
}
