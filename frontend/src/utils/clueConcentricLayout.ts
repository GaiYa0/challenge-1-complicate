import type { EdgeData, NodeData } from '@antv/g6'

import type { ClueListItem } from '../api/clue'

/** 同心圆三层半径（像素），中心为人物 */
export const CLUE_RING_RADII = {
  high: 120,
  medium: 200,
  low: 280,
} as const

export type ClueRiskRing = keyof typeof CLUE_RING_RADII

const RING_ORDER: ClueRiskRing[] = ['high', 'medium', 'low']

export function normalizeRiskLevel(raw: string): ClueRiskRing {
  const s = String(raw || '').toLowerCase()
  if (s === 'high' || s === 'medium' || s === 'low') return s
  return 'low'
}

/** 按 risk_level 分桶（未识别归入 low） */
export function groupCluesByRiskLevel(clues: ClueListItem[]): Record<ClueRiskRing, ClueListItem[]> {
  const out: Record<ClueRiskRing, ClueListItem[]> = { high: [], medium: [], low: [] }
  for (const c of clues) {
    out[normalizeRiskLevel(c.risk_level)].push(c)
  }
  return out
}

export interface CluePlacedNode {
  clue: ClueListItem
  ring: ClueRiskRing
  x: number
  y: number
  indexInRing: number
  countInRing: number
}

/**
 * angle = 2π * i / n，每层独立按节点数均分圆周。
 */
export function layoutConcentricClueNodes(
  centerX: number,
  centerY: number,
  clues: ClueListItem[],
): CluePlacedNode[] {
  const grouped = groupCluesByRiskLevel(clues)
  const placed: CluePlacedNode[] = []
  for (const ring of RING_ORDER) {
    const list = grouped[ring]
    const n = list.length
    const r = CLUE_RING_RADII[ring]
    if (n === 0) continue
    for (let i = 0; i < n; i++) {
      const angle = (2 * Math.PI * i) / n
      placed.push({
        clue: list[i],
        ring,
        x: centerX + r * Math.cos(angle),
        y: centerY + r * Math.sin(angle),
        indexInRing: i,
        countInRing: n,
      })
    }
  }
  return placed
}

export const CLUE_CENTER_ID = '__clue_center__'

const RISK_STYLE: Record<
  ClueRiskRing,
  { fill: string; stroke: string; labelFill: string }
> = {
  high: { fill: '#fecaca', stroke: '#b91c1c', labelFill: '#7f1d1d' },
  medium: { fill: '#fef9c3', stroke: '#ca8a04', labelFill: '#713f12' },
  low: { fill: '#dbeafe', stroke: '#2563eb', labelFill: '#1e3a8a' },
}

function truncateTitle(s: string, max = 18): string {
  const t = String(s || '').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max)}…`
}

/** 将线索列表转为 G6 数据：中心人物 + 同心圆上的线索节点 + 辐射边 */
export function cluesToGraphData(
  centerX: number,
  centerY: number,
  personLabel: string,
  clues: ClueListItem[],
): { nodes: NodeData[]; edges: EdgeData[] } {
  const placed = layoutConcentricClueNodes(centerX, centerY, clues)
  const nodes: NodeData[] = [
    {
      id: CLUE_CENTER_ID,
      type: 'diamond',
      data: { kind: 'center', label: personLabel },
      style: {
        x: centerX,
        y: centerY,
        size: 56,
        fill: '#f8fafc',
        stroke: '#0f172a',
        lineWidth: 3,
        labelText: personLabel,
        labelPlacement: 'bottom',
        labelOffsetY: 10,
        labelFontSize: 13,
        labelFontWeight: 700,
        labelFill: '#0f172a',
        labelBackground: true,
        labelBackgroundFill: 'rgba(255,255,255,0.95)',
        labelPadding: [4, 8, 4, 8],
        shadowColor: 'rgba(15,23,42,0.2)',
        shadowBlur: 10,
      },
    },
  ]
  const edges: EdgeData[] = []
  for (const p of placed) {
    const id = `clue-${p.clue.id}`
    const palette = RISK_STYLE[p.ring]
    nodes.push({
      id,
      type: 'circle',
      data: {
        kind: 'clue',
        clueId: p.clue.id,
        title: p.clue.title,
        risk_level: p.clue.risk_level,
        ring: p.ring,
      },
      style: {
        x: p.x,
        y: p.y,
        size: 44,
        fill: palette.fill,
        stroke: palette.stroke,
        lineWidth: 2,
        labelText: truncateTitle(p.clue.title),
        labelPlacement: 'bottom',
        labelOffsetY: 8,
        labelFontSize: 11,
        labelFill: palette.labelFill,
        labelBackground: true,
        labelBackgroundFill: 'rgba(255,255,255,0.92)',
        labelPadding: [2, 6, 2, 6],
        labelMaxWidth: 140,
      },
    })
    edges.push({
      id: `e-${p.clue.id}`,
      source: CLUE_CENTER_ID,
      target: id,
    })
  }
  return { nodes, edges }
}
