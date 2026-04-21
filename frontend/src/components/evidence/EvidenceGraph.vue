<script setup lang="ts">
import { Graph, NodeEvent } from '@antv/g6'
import type { IEvent, IPointerEvent, Node as G6Node, NodeData, EdgeData } from '@antv/g6'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EvidenceGraphData, EvidenceNodeKind, ActionType } from '../../types/evidence'
import { NODE_KIND_COLORS } from '../../types/evidence'

const R1 = 200
const R2 = 340
const SUSPECT_SIZE = 56
const BEHAVIOR_SIZE = 36
const EVIDENCE_SIZE = 22
const MAX_EV_PER_BEHAVIOR = 5
const RENDER_CAP = 120
const OVERLAP_MIN = 20

const props = withDefaults(
  defineProps<{
    data: EvidenceGraphData | null
    loading?: boolean
    highlightChainId?: string | null
    playbackIndex?: number
    filterType?: ActionType | 'all'
  }>(),
  { loading: false, highlightChainId: null, playbackIndex: -1, filterType: 'all' },
)

const emit = defineEmits<{
  (e: 'node-click', payload: { id: string; kind: EvidenceNodeKind; data: Record<string, unknown> }): void
  (e: 'chain-count', count: number): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null
let resizeObs: ResizeObserver | null = null
let unbind: (() => void) | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let lastSig = ''

interface BehaviorCluster {
  index: number
  behaviorId: string
  evidenceIds: string[]
  collapsedCount: number
}

function getSize(el: HTMLDivElement): [number, number] {
  const w = Math.max(600, Math.floor(el.clientWidth || el.getBoundingClientRect().width))
  const h = Math.max(600, Math.floor(el.clientHeight || el.getBoundingClientRect().height || 600))
  return [w, h]
}

function nodeIdFromEvt(evt: IEvent): string | null {
  const e = evt as IPointerEvent<G6Node>
  if (e.targetType !== 'node' || !e.target) return null
  const raw = (e.target as unknown as { id?: string | number }).id
  return raw != null ? String(raw) : null
}

function sig(d: EvidenceGraphData | null, ft: string, pi: number): string {
  if (!d) return ''
  return `${d.nodes.length}:${d.edges.length}:${ft}:${pi}`
}

function buildClusters(data: EvidenceGraphData): BehaviorCluster[] {
  const behaviors = data.nodes.filter((n) => n.kind === 'action').slice(0, RENDER_CAP)
  return behaviors.map((b, i) => {
    const allEvIds: string[] = []
    for (const edge of data.edges) {
      if (edge.source === b.id) {
        const t = data.nodes.find((n) => n.id === edge.target && n.kind === 'evidence')
        if (t) allEvIds.push(t.id)
      }
    }
    const kept = allEvIds.slice(0, MAX_EV_PER_BEHAVIOR)
    return { index: i, behaviorId: b.id, evidenceIds: kept, collapsedCount: allEvIds.length - kept.length }
  })
}

function radialPositions(
  data: EvidenceGraphData,
  clusters: BehaviorCluster[],
  cx: number,
  cy: number,
): Map<string, { x: number; y: number }> {
  const pos = new Map<string, { x: number; y: number }>()
  const N = Math.max(1, clusters.length)
  const totalNodes = data.nodes.length
  const r1 = totalNodes > 120 ? R1 * 0.8 : R1
  const r2 = totalNodes > 120 ? R2 * 0.85 : R2

  for (const s of data.nodes.filter((n) => n.kind === 'suspect')) {
    pos.set(s.id, { x: cx, y: cy })
  }

  for (const cl of clusters) {
    const angle = (2 * Math.PI / N) * cl.index - Math.PI / 2
    const bx = cx + r1 * Math.cos(angle)
    const by = cy + r1 * Math.sin(angle)
    pos.set(cl.behaviorId, { x: bx, y: by })

    const evCount = cl.evidenceIds.length + (cl.collapsedCount > 0 ? 1 : 0)
    const spreadRange = Math.min(0.5, 0.15 * evCount)

    for (let j = 0; j < cl.evidenceIds.length; j++) {
      const offset = evCount > 1 ? (j - (evCount - 1) / 2) * (spreadRange * 2 / Math.max(1, evCount - 1)) : 0
      const ea = angle + offset
      pos.set(cl.evidenceIds[j], {
        x: cx + r2 * Math.cos(ea),
        y: cy + r2 * Math.sin(ea),
      })
    }

    if (cl.collapsedCount > 0) {
      const colId = `collapse-${cl.behaviorId}`
      const offset = evCount > 1 ? ((evCount - 1) - (evCount - 1) / 2) * (spreadRange * 2 / Math.max(1, evCount - 1)) : 0
      const ea = angle + offset
      pos.set(colId, {
        x: cx + r2 * Math.cos(ea),
        y: cy + r2 * Math.sin(ea),
      })
    }
  }

  for (const n of data.nodes) {
    if (!pos.has(n.id)) {
      pos.set(n.id, { x: cx, y: cy })
    }
  }

  resolveOverlaps(pos)
  return pos
}

function resolveOverlaps(pos: Map<string, { x: number; y: number }>) {
  const entries = [...pos.entries()]
  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      const a = entries[i][1]
      const b = entries[j][1]
      const dx = a.x - b.x
      const dy = a.y - b.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < OVERLAP_MIN && dist > 0) {
        const nx = dx / dist
        const ny = dy / dist
        b.x -= nx * (OVERLAP_MIN - dist)
        b.y -= ny * (OVERLAP_MIN - dist)
      } else if (dist === 0) {
        b.x += OVERLAP_MIN
      }
    }
  }
}

function isValidEdge(
  src: string, tgt: string,
  kindMap: Map<string, EvidenceNodeKind>,
  orderMap: Map<string, number>,
): boolean {
  const sk = kindMap.get(src)
  const tk = kindMap.get(tgt)
  if (!sk || !tk) return false
  if (sk === 'suspect' && tk === 'action') return true
  if (sk === 'action' && tk === 'evidence') return true
  if (sk === 'action' && tk === 'action') {
    const si = orderMap.get(src) ?? -1
    const ti = orderMap.get(tgt) ?? -1
    return ti === si + 1
  }
  return false
}

let activeChainNodes = new Set<string>()
let activeChainEdges = new Set<string>()

function highlightCluster(behaviorId: string) {
  if (!graph || graph.destroyed || !props.data) return
  clearHighlight()
  const related = new Set<string>([behaviorId])
  const relEdges = new Set<string>()
  for (const e of props.data.edges) {
    if (e.source === behaviorId || e.target === behaviorId) {
      related.add(e.source)
      related.add(e.target)
      relEdges.add(e.id)
    }
  }
  props.data.nodes.filter((n) => n.kind === 'suspect').forEach((n) => related.add(n.id))
  for (const e of props.data.edges) {
    if (related.has(e.source) && related.has(e.target)) relEdges.add(e.id)
  }
  activeChainNodes = related
  activeChainEdges = relEdges
  try {
    for (const nId of related) { if (graph.hasNode(nId)) void graph.setElementState(nId, 'active') }
    for (const eId of relEdges) { if (graph.hasEdge(eId)) void graph.setElementState(eId, 'active') }
  } catch { /* */ }
}

function clearHighlight() {
  if (!graph || graph.destroyed) return
  try {
    for (const nId of activeChainNodes) { if (graph.hasNode(nId)) void graph.setElementState(nId, []) }
    for (const eId of activeChainEdges) { if (graph.hasEdge(eId)) void graph.setElementState(eId, []) }
  } catch { /* */ }
  activeChainNodes = new Set()
  activeChainEdges = new Set()
}

async function mountGraph() {
  const el = containerRef.value
  if (!el || props.loading || !props.data || props.data.nodes.length === 0) {
    destroyGraph(); lastSig = ''; return
  }
  const s = sig(props.data, props.filterType, props.playbackIndex)
  if (s === lastSig && graph && !graph.destroyed) return
  lastSig = s
  destroyGraph()

  const filteredData = props.filterType === 'all' ? props.data : (() => {
    const va = new Set<string>()
    for (const e of props.data.edges) { if (e.actionType === props.filterType) va.add(e.source) }
    const ri = new Set<string>()
    props.data.nodes.filter((n) => n.kind === 'suspect').forEach((n) => ri.add(n.id))
    for (const e of props.data.edges) {
      if (va.has(e.source) || va.has(e.target)) { ri.add(e.source); ri.add(e.target) }
    }
    return {
      nodes: props.data.nodes.filter((n) => ri.has(n.id)),
      edges: props.data.edges.filter((e) => ri.has(e.source) && ri.has(e.target)),
    }
  })()

  const clusters = buildClusters(filteredData)
  const playbackCutoff = props.playbackIndex >= 0 ? props.playbackIndex : clusters.length
  const visClusters = clusters.slice(0, playbackCutoff)
  emit('chain-count', clusters.length)

  const visNodeIds = new Set<string>()
  filteredData.nodes.filter((n) => n.kind === 'suspect').forEach((n) => visNodeIds.add(n.id))
  for (const cl of visClusters) {
    visNodeIds.add(cl.behaviorId)
    cl.evidenceIds.forEach((id) => visNodeIds.add(id))
  }

  const [cw, ch] = getSize(el)
  const cx = cw / 2
  const cy = ch / 2
  const positions = radialPositions(filteredData, visClusters, cx, cy)

  const kindMap = new Map<string, EvidenceNodeKind>()
  const orderMap = new Map<string, number>()
  visClusters.forEach((cl, i) => orderMap.set(cl.behaviorId, i))

  const g6Nodes: NodeData[] = []
  for (const n of filteredData.nodes) {
    if (!visNodeIds.has(n.id)) continue
    kindMap.set(n.id, n.kind)
    const p = positions.get(n.id) ?? { x: cx, y: cy }
    g6Nodes.push({
      id: n.id,
      data: { label: n.label, kind: n.kind, ...(n.data ?? {}) },
      style: { x: p.x, y: p.y },
    })
  }
  for (const cl of visClusters) {
    if (cl.collapsedCount > 0) {
      const colId = `collapse-${cl.behaviorId}`
      kindMap.set(colId, 'evidence')
      const p = positions.get(colId) ?? { x: cx, y: cy }
      g6Nodes.push({
        id: colId,
        data: { label: `+${cl.collapsedCount}`, kind: 'evidence', isCollapse: true },
        style: { x: p.x, y: p.y },
      })
    }
  }

  const nodeIdSet = new Set(g6Nodes.map((n) => String(n.id)))
  const suspectIds = filteredData.nodes.filter((n) => n.kind === 'suspect').map((n) => n.id)
  const rawEdges: EdgeData[] = []

  for (const sId of suspectIds) {
    for (const cl of visClusters) {
      rawEdges.push({ id: `e-s-${sId}-${cl.behaviorId}`, source: sId, target: cl.behaviorId, data: { label: '', edgeType: 'main' } })
    }
  }
  for (let i = 0; i < visClusters.length - 1; i++) {
    rawEdges.push({ id: `e-chain-${i}`, source: visClusters[i].behaviorId, target: visClusters[i + 1].behaviorId, data: { label: '', edgeType: 'timeline' } })
  }
  for (const cl of visClusters) {
    for (const evId of cl.evidenceIds) {
      const orig = filteredData.edges.find((e) => e.source === cl.behaviorId && e.target === evId)
      rawEdges.push({
        id: orig?.id ?? `e-b-${cl.behaviorId}-${evId}`,
        source: cl.behaviorId, target: evId,
        data: {
          label: orig?.label ?? '',
          actionType: orig?.actionType ?? '',
          edgeType: 'secondary',
          weight: typeof orig?.weight === 'number' ? orig.weight : undefined,
        },
      })
    }
    if (cl.collapsedCount > 0) {
      rawEdges.push({ id: `e-col-${cl.behaviorId}`, source: cl.behaviorId, target: `collapse-${cl.behaviorId}`, data: { label: '', edgeType: 'secondary' } })
    }
  }

  const validEdges = rawEdges.filter((e) =>
    nodeIdSet.has(String(e.source)) && nodeIdSet.has(String(e.target)) &&
    isValidEdge(String(e.source), String(e.target), kindMap, orderMap),
  )

  graph = new Graph({
    container: el,
    width: cw,
    height: ch,
    autoResize: false,
    data: { nodes: g6Nodes, edges: validEdges },
    node: {
      style: (nd: NodeData) => {
        const d = nd.data as { label?: string; kind?: EvidenceNodeKind; isCollapse?: boolean } | undefined
        const kind = d?.kind ?? 'evidence'
        const isCol = d?.isCollapse === true
        const colors = NODE_KIND_COLORS[kind] ?? NODE_KIND_COLORS.evidence
        const label = d?.label ?? String(nd.id)
        const size = kind === 'suspect' ? SUSPECT_SIZE : kind === 'action' ? BEHAVIOR_SIZE : EVIDENCE_SIZE
        return {
          type: 'circle',
          size,
          fill: isCol ? '#f3f4f6' : colors.fill,
          stroke: isCol ? '#9ca3af' : colors.stroke,
          lineWidth: kind === 'suspect' ? 3 : kind === 'action' ? 2 : 1.5,
          shadowColor: kind === 'suspect' ? 'rgba(220,38,38,0.3)' : kind === 'evidence' && !isCol ? 'rgba(202,138,4,0.3)' : 'transparent',
          shadowBlur: kind === 'suspect' ? 16 : kind === 'evidence' && !isCol ? 8 : 0,
          labelText: label.length > 8 ? label.slice(0, 7) + '...' : label,
          labelPlacement: 'bottom' as const,
          labelOffsetY: kind === 'suspect' ? 16 : kind === 'action' ? 12 : 8,
          labelFontSize: kind === 'suspect' ? 14 : kind === 'action' ? 12 : 10,
          labelFill: isCol ? '#6b7280' : colors.text,
          labelFontWeight: kind === 'suspect' ? 'bold' : 'normal',
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.95)',
          labelPadding: [1, 6, 1, 6] as [number, number, number, number],
          labelMaxWidth: kind === 'evidence' ? 100 : 140,
          labelMaxLines: 1,
          labelTextOverflow: 'ellipsis' as const,
          cursor: isCol ? 'default' : 'pointer',
        }
      },
      state: {
        active: { lineWidth: 4, shadowBlur: 20, shadowColor: 'rgba(37,99,235,0.5)' },
      },
    },
    edge: {
      type: 'line',
      style: (ed: EdgeData) => {
        const d = ed.data as {
          label?: string
          actionType?: string
          edgeType?: string
          weight?: number
        } | undefined
        const et = d?.edgeType ?? 'secondary'
        const at = d?.actionType ?? ''
        const isMain = et === 'main'
        const isTL = et === 'timeline'
        const secW = d?.weight
        const color = isTL ? '#94a3b8' : at === 'fund' ? '#dc2626' : at === 'call' ? '#ea580c' : at === 'trip' ? '#2563eb' : isMain ? '#475569' : '#94a3b8'
        const secLine =
          isMain ? 2
          : isTL ? 1.5
          : secW != null && secW > 0 ? Math.min(6, 1 + Math.log10(1 + secW) * 1.2)
          : 1
        return {
          stroke: color,
          lineWidth: secLine,
          opacity: isMain ? 1 : isTL ? 0.35 : secW != null ? 0.32 : 0.2,
          endArrow: true,
          labelText: d?.label ?? '',
          labelFontSize: 9,
          labelFill: '#64748b',
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.92)',
          labelPadding: [1, 3, 1, 3] as [number, number, number, number],
          lineDash: isTL ? [4, 3] : undefined,
        }
      },
      state: {
        active: { lineWidth: 2.5, stroke: '#2563eb', opacity: 1, endArrow: true },
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas'],
  })

  const onClick = (evt: IEvent) => {
    const id = nodeIdFromEvt(evt)
    if (!id || !graph || graph.destroyed || !graph.hasNode(id)) return
    const nd = graph.getNodeData(id)
    const d = nd.data as { kind?: EvidenceNodeKind; isCollapse?: boolean } | undefined
    if (d?.isCollapse) return
    const kind = d?.kind ?? 'evidence'
    if (kind === 'action') highlightCluster(id)
    else clearHighlight()
    emit('node-click', { id, kind, data: (nd.data as Record<string, unknown>) ?? {} })
  }
  graph.on(NodeEvent.CLICK, onClick)
  unbind = () => { try { graph?.off(NodeEvent.CLICK, onClick) } catch { /* */ } }

  await graph.render()
  await graph.fitView(undefined, false)

  resizeObs = new ResizeObserver(() => {
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      if (!graph || graph.destroyed || !el) return
      const [w, h] = getSize(el)
      graph.resize(w, h)
      void graph.fitView(undefined, false)
    }, 150)
  })
  resizeObs.observe(el)
}

function destroyGraph() {
  resizeObs?.disconnect(); resizeObs = null
  unbind?.(); unbind = null
  if (resizeTimer) { clearTimeout(resizeTimer); resizeTimer = null }
  if (graph && !graph.destroyed) graph.destroy()
  graph = null
}

onMounted(() => void mountGraph())
watch(() => [props.data, props.loading, props.highlightChainId, props.playbackIndex, props.filterType], () => void mountGraph(), { deep: true })
onBeforeUnmount(() => destroyGraph())

defineExpose({ highlightCluster, clearHighlight })
</script>

<template>
  <div class="ev-radial-graph">
    <div class="ring-legend">
      <span class="rl-item"><span class="rl-dot" style="background:#dc2626" /> 嫌疑人（中心）</span>
      <span class="rl-item"><span class="rl-dot" style="background:#2563eb" /> 行为（内环）</span>
      <span class="rl-item"><span class="rl-dot" style="background:#ca8a04" /> 证据（外环）</span>
    </div>
    <div class="canvas-wrap" v-loading="loading">
      <div v-if="!data || data.nodes.length === 0" class="empty-canvas">
        暂无证据关系数据
      </div>
      <div v-show="data && data.nodes.length > 0" ref="containerRef" class="canvas" />
    </div>
  </div>
</template>

<style scoped>
.ev-radial-graph { width: 100%; position: relative; }
.ring-legend {
  display: flex; gap: 20px; justify-content: center;
  margin-bottom: 10px; font-size: 12px; color: var(--app-text-secondary);
}
.rl-item { display: flex; align-items: center; gap: 5px; }
.rl-dot { width: 10px; height: 10px; border-radius: 50%; }
.canvas-wrap { min-height: 640px; position: relative; }
.canvas {
  width: 100%; min-height: 640px; height: 75vh;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: radial-gradient(circle at 50% 50%, rgba(37,99,235,0.03) 0%, transparent 60%), var(--app-bg-card);
}
.empty-canvas {
  display: flex; align-items: center; justify-content: center;
  min-height: 500px; color: var(--app-text-secondary); font-size: 14px;
}
</style>
