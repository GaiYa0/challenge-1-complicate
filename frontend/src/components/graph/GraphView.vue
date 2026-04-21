<script setup lang="ts">
import { Graph, GraphEvent, NodeEvent } from '@antv/g6'
import type { EdgeData, IEvent, IPointerEvent, LayoutOptions, Node as G6Node, NodeData } from '@antv/g6'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { clipGraphVisualization, GRAPH_DISPLAY_MAX_NODES } from '../../utils/graphClip'

export type Neo4jGraphPayload = {
  nodes: { id: string; label: string }[]
  edges: { id: string; source: string; target: string }[]
}

export type GraphLayoutKind = 'force' | 'dagre' | 'radial'

const LABEL_FONT_SIZE = 12
const LABEL_LINE_HEIGHT = 16
const LABEL_MAX_CHARS = 10
const LABEL_MAX_WIDTH = 140
const PAD_X = 10
const MIN_NODE_DIAM = 36
const MAX_NODE_DIAM = 64
const LAYOUT_PADDING = 28
const PARALLEL_EDGE_GAP = 28
const HARD_RENDER_CAP = 300
const SIMPLIFY_THRESHOLD = 100

const props = withDefaults(
  defineProps<{
    variant?: 'demo' | 'neo4j'
    neo4jData?: Neo4jGraphPayload | null
    loading?: boolean
    totalNodes?: number
    initialCap?: number
    maxNeoNodes?: number
    showHeading?: boolean
    layout?: GraphLayoutKind
  }>(),
  {
    variant: 'demo',
    neo4jData: null,
    loading: false,
    totalNodes: 48,
    initialCap: 48,
    maxNeoNodes: GRAPH_DISPLAY_MAX_NODES,
    showHeading: true,
    layout: undefined,
  },
)

const emit = defineEmits<{
  (e: 'node-click', payload: { id: string; data: NodeData }): void
  (e: 'node-hover', payload: { id: string | null; data: NodeData | null }): void
  (e: 'update:layout', value: GraphLayoutKind): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null
let resizeObserver: ResizeObserver | null = null
let afterLayoutFitHandler: (() => void) | null = null

const internalLayout = ref<GraphLayoutKind>('force')
const activeLayout = computed<GraphLayoutKind>({
  get: () => props.layout ?? internalLayout.value,
  set: (v) => {
    if (props.layout === undefined) internalLayout.value = v
    emit('update:layout', v)
  },
})

let hoveredNodeId: string | null = null
let lastSignature = ''

function stableEdgeSignature(
  nodes: ReadonlyArray<{ id: string; label?: string }>,
  edges: ReadonlyArray<{ id: string; source: string; target: string }>,
  layout: GraphLayoutKind,
  variant: string,
): string {
  const n = nodes.map((x) => `${x.id}|${x.label ?? ''}`).sort().join(';')
  const e = edges.map((x) => `${x.source}>${x.target}`).sort().join(';')
  return `${variant}::${layout}::${nodes.length}::${edges.length}::${n}::${e}`
}

function measureLabelWidth(text: string, fontSize = LABEL_FONT_SIZE): number {
  if (typeof document === 'undefined') return text.length * (fontSize * 0.6)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return text.length * (fontSize * 0.6)
  ctx.font = `${fontSize}px system-ui, -apple-system, sans-serif`
  return ctx.measureText(text).width
}

function truncateLabel(text: string, max = LABEL_MAX_CHARS): string {
  if (text == null) return ''
  const s = String(text)
  if (s.length <= max) return s
  return s.slice(0, Math.max(1, max - 1)) + '…'
}

function computeNodeDiameter(label: string): number {
  const t = truncateLabel(label)
  const tw = measureLabelWidth(t, LABEL_FONT_SIZE)
  const d = Math.ceil(tw + PAD_X * 2)
  return Math.min(MAX_NODE_DIAM, Math.max(MIN_NODE_DIAM, d))
}

function layoutSizeFor(label: string): number {
  return computeNodeDiameter(label) + LAYOUT_PADDING
}

function forceTierParams(n: number) {
  if (n < 30) {
    return {
      linkDistance: 180,
      nodeStrength: -300,
      collideStrength: 1.0,
      edgeStrength: 0.5,
      nodeSpacing: 20,
    }
  }
  if (n <= 100) {
    return {
      linkDistance: 260,
      nodeStrength: -500,
      collideStrength: 1.2,
      edgeStrength: 0.4,
      nodeSpacing: 24,
    }
  }
  return {
    linkDistance: 360,
    nodeStrength: -800,
    collideStrength: 1.5,
    edgeStrength: 0.3,
    nodeSpacing: 28,
  }
}

function buildNodeSizeFn(): (n: NodeData) => number {
  return (n: NodeData) => {
    const raw = n.data as { label?: string; layoutSize?: number } | undefined
    if (raw?.layoutSize != null && Number.isFinite(raw.layoutSize)) {
      return raw.layoutSize as number
    }
    const text = raw?.label != null ? String(raw.label) : String(n.id ?? '')
    return layoutSizeFor(text)
  }
}

function buildForceLayoutOptions(
  nodeCount: number,
  nodeSizeFn: (n: NodeData) => number,
): LayoutOptions {
  const t = forceTierParams(nodeCount)
  return {
    type: 'force',
    preventOverlap: true,
    nodeSize: (node: NodeData) => nodeSizeFn(node),
    nodeSpacing: t.nodeSpacing,
    linkDistance: t.linkDistance,
    nodeStrength: t.nodeStrength,
    edgeStrength: t.edgeStrength,
    collideStrength: t.collideStrength,
    alphaDecay: 0.022,
    alphaMin: 0.02,
    animation: false,
  }
}

function buildDagreLayout(nodeSizeFn: (n: NodeData) => number): LayoutOptions {
  return {
    type: 'dagre',
    rankdir: 'LR',
    nodesep: 52,
    ranksep: 80,
    nodeSize: (node: NodeData) => nodeSizeFn(node),
  }
}

function buildRadialLayout(
  nodeCount: number,
  nodeSizeFn: (n: NodeData) => number,
  focusNodeId?: string | null,
): LayoutOptions {
  const t = forceTierParams(nodeCount)
  return {
    type: 'radial',
    linkDistance: t.linkDistance,
    unitRadius: null,
    preventOverlap: true,
    nodeSize: (node: NodeData) => nodeSizeFn(node),
    nodeSpacing: t.nodeSpacing,
    maxPreventOverlapIteration: 240,
    focusNode: focusNodeId ?? undefined,
  }
}

function resolveLayout(
  kind: GraphLayoutKind,
  nodeCount: number,
  nodeSizeFn: (n: NodeData) => number,
  focusId: string | null,
): LayoutOptions {
  if (kind === 'force') return buildForceLayoutOptions(nodeCount, nodeSizeFn)
  if (kind === 'dagre') return buildDagreLayout(nodeSizeFn)
  return buildRadialLayout(nodeCount, nodeSizeFn, focusId)
}

function getCanvasSize(el: HTMLDivElement): [number, number] {
  const rect = el.getBoundingClientRect()
  const w = Math.max(1, Math.floor(el.clientWidth || rect.width))
  const hRaw = el.clientHeight || rect.height
  const h = Math.max(500, Math.floor(hRaw > 0 ? hRaw : 500))
  return [w, h]
}

function bindResize(el: HTMLDivElement) {
  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver(() => {
    if (!graph || graph.destroyed) return
    const [w, h] = getCanvasSize(el)
    if (w > 0 && h > 0) {
      try {
        graph.resize(w, h)
        void graph.fitView(undefined, false)
      } catch {
        /* noop */
      }
    }
  })
  resizeObserver.observe(el)
}

function seedInitialPositions(nodes: NodeData[], width: number, height: number): NodeData[] {
  if (nodes.length === 0) return nodes
  const cx = width / 2
  const cy = height / 2
  const baseR = Math.max(120, Math.min(width, height) * 0.36)
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))
  return nodes.map((n, i) => {
    const angle = i * goldenAngle + Math.random() * 0.8
    const radius = baseR * Math.sqrt((i + 1) / nodes.length) * (0.7 + Math.random() * 0.55)
    const x = cx + Math.cos(angle) * radius + (Math.random() - 0.5) * 16
    const y = cy + Math.sin(angle) * radius + (Math.random() - 0.5) * 16
    const prev = (n as unknown as { style?: Record<string, unknown> }).style ?? {}
    return { ...n, style: { ...prev, x, y } } as NodeData
  })
}

function annotateParallelEdges(edges: EdgeData[]): EdgeData[] {
  const counts = new Map<string, number>()
  const indices = new Map<string, number>()
  for (const e of edges) {
    const a = String(e.source)
    const b = String(e.target)
    const key = a < b ? `${a}::${b}` : `${b}::${a}`
    const c = counts.get(key) ?? 0
    indices.set(String(e.id), c)
    counts.set(key, c + 1)
  }
  return edges.map((e) => {
    const a = String(e.source)
    const b = String(e.target)
    const key = a < b ? `${a}::${b}` : `${b}::${a}`
    const total = counts.get(key) ?? 1
    if (total <= 1) {
      return { ...e, data: { ...(e.data as object | undefined), curveOffset: 0, parallelTotal: 1 } }
    }
    const idx = indices.get(String(e.id)) ?? 0
    const offset = (idx - (total - 1) / 2) * PARALLEL_EDGE_GAP
    return {
      ...e,
      data: { ...(e.data as object | undefined), curveOffset: offset, parallelTotal: total },
    }
  })
}

function hardCap(nodes: NodeData[], edges: EdgeData[]): { nodes: NodeData[]; edges: EdgeData[] } {
  if (nodes.length <= HARD_RENDER_CAP) return { nodes, edges }
  const kept = new Set(nodes.slice(0, HARD_RENDER_CAP).map((n) => String(n.id)))
  return {
    nodes: nodes.slice(0, HARD_RENDER_CAP),
    edges: edges.filter((e) => kept.has(String(e.source)) && kept.has(String(e.target))),
  }
}

function clearHoverHighlight() {
  if (!graph || graph.destroyed) return
  try {
    if (hoveredNodeId && graph.hasNode(hoveredNodeId)) {
      void graph.setElementState(hoveredNodeId, [])
    }
    const edges = graph.getEdgeData()
    for (const e of edges) {
      if (e.id && graph.hasEdge(e.id)) void graph.setElementState(e.id, [])
    }
  } catch {
    /* noop */
  }
  hoveredNodeId = null
}

function applyHoverHighlight(nodeId: string) {
  if (!graph || graph.destroyed) return
  clearHoverHighlight()
  hoveredNodeId = nodeId
  try {
    if (graph.hasNode(nodeId)) void graph.setElementState(nodeId, 'active')
    const related = graph.getRelatedEdgesData(nodeId)
    for (const e of related) {
      if (e.id && graph.hasEdge(e.id)) void graph.setElementState(e.id, 'active')
    }
  } catch {
    /* noop */
  }
}

function nodeIdFromPointer(evt: IEvent): string | null {
  const e = evt as IPointerEvent<G6Node>
  if (e.targetType !== 'node' || !e.target) return null
  const raw = (e.target as unknown as { id?: string | number }).id
  return raw != null ? String(raw) : null
}

function bindGraphInteractions(g: Graph) {
  const onEnter = (evt: IEvent) => {
    const id = nodeIdFromPointer(evt)
    if (!id || !g.hasNode(id)) return
    applyHoverHighlight(id)
    emit('node-hover', { id, data: g.getNodeData(id) })
  }
  const onLeave = () => {
    clearHoverHighlight()
    emit('node-hover', { id: null, data: null })
  }
  const onClick = (evt: IEvent) => {
    const id = nodeIdFromPointer(evt)
    if (!id || !g.hasNode(id)) return
    emit('node-click', { id, data: g.getNodeData(id) })
  }
  g.on(NodeEvent.POINTER_ENTER, onEnter)
  g.on(NodeEvent.POINTER_LEAVE, onLeave)
  g.on(NodeEvent.CLICK, onClick)
  return () => {
    try {
      g.off(NodeEvent.POINTER_ENTER, onEnter)
      g.off(NodeEvent.POINTER_LEAVE, onLeave)
      g.off(NodeEvent.CLICK, onClick)
    } catch {
      /* noop */
    }
  }
}

let unbindInteractions: (() => void) | null = null

function destroyGraph() {
  unbindInteractions?.()
  unbindInteractions = null
  if (afterLayoutFitHandler && graph && !graph.destroyed) {
    try {
      graph.off(GraphEvent.AFTER_LAYOUT, afterLayoutFitHandler)
    } catch {
      /* noop */
    }
  }
  afterLayoutFitHandler = null
  if (graph && !graph.destroyed) {
    try {
      graph.destroy()
    } catch {
      /* noop */
    }
  }
  graph = null
}

async function mountGraph() {
  const el = containerRef.value
  if (!el) return

  if (props.loading) {
    destroyGraph()
    lastSignature = ''
    return
  }

  let nodes: NodeData[] = []
  let edges: EdgeData[] = []
  let focusId: string | null = null

  if (props.variant === 'neo4j') {
    const raw = props.neo4jData
    if (!raw || (raw.nodes.length === 0 && raw.edges.length === 0)) {
      destroyGraph()
      lastSignature = ''
      return
    }
    const d = clipGraphVisualization(
      { nodes: raw.nodes, edges: raw.edges },
      Math.max(2, props.maxNeoNodes ?? GRAPH_DISPLAY_MAX_NODES),
    )
    nodes = d.nodes.map((n) => {
      const label = String(n.label ?? n.id)
      return { id: n.id, data: { label, layoutSize: layoutSizeFor(label) } }
    })
    edges = d.edges.map((e) => ({ id: e.id, source: e.source, target: e.target }))
    focusId = nodes[0]?.id != null ? String(nodes[0].id) : null
  } else {
    destroyGraph()
    lastSignature = ''
    return
  }

  const capped = hardCap(nodes, edges)
  nodes = capped.nodes
  edges = annotateParallelEdges(capped.edges)

  const sig = stableEdgeSignature(
    nodes.map((n) => ({ id: String(n.id), label: (n.data as { label?: string })?.label })),
    edges.map((e) => ({ id: String(e.id), source: String(e.source), target: String(e.target) })),
    activeLayout.value,
    props.variant,
  )
  if (sig === lastSignature && graph && !graph.destroyed) {
    return
  }
  lastSignature = sig

  destroyGraph()

  const [width, height] = getCanvasSize(el)
  const nCount = nodes.length
  const simplify = nCount > SIMPLIFY_THRESHOLD
  const nodeSizeFn = buildNodeSizeFn()
  const layout = resolveLayout(activeLayout.value, nCount, nodeSizeFn, focusId)

  const seededNodes = seedInitialPositions(nodes, width, height)
  const isNeo = props.variant === 'neo4j'

  graph = new Graph({
    container: el,
    width,
    height,
    autoResize: false,
    data: { nodes: seededNodes, edges },
    layout,
    node: {
      style: (data: NodeData) => {
        const rawData = data.data as { label?: string } | undefined
        const text = rawData?.label != null ? String(rawData.label) : String(data.id ?? '')
        const display = truncateLabel(text)
        const size = simplify ? Math.max(18, MIN_NODE_DIAM - 14) : computeNodeDiameter(text)
        return {
          type: 'circle',
          size,
          fill: isNeo ? '#e0e7ff' : '#f1f5f9',
          stroke: isNeo ? '#6366f1' : '#64748b',
          lineWidth: 1,
          labelText: simplify ? '' : display,
          labelPlacement: 'bottom',
          labelOffsetY: 10,
          labelFontSize: LABEL_FONT_SIZE,
          labelFill: isNeo ? '#1f2937' : '#334155',
          labelBackground: true,
          labelBackgroundFill: 'rgba(255,255,255,0.94)',
          labelPadding: [2, 6, 2, 6],
          labelLineHeight: LABEL_LINE_HEIGHT,
          labelWordWrap: true,
          labelMaxWidth: LABEL_MAX_WIDTH,
          labelMaxLines: 1,
          labelTextOverflow: 'ellipsis',
        }
      },
      state: {
        active: {
          fill: isNeo ? '#c7d2fe' : '#dbeafe',
          stroke: isNeo ? '#4338ca' : '#2563eb',
          lineWidth: 2,
          shadowColor: isNeo ? 'rgba(67,56,202,0.35)' : 'rgba(37,99,235,0.3)',
          shadowBlur: isNeo ? 12 : 10,
        },
      },
    },
    edge: {
      type: (data: EdgeData) => {
        const d = data.data as { curveOffset?: number } | undefined
        return d?.curveOffset ? 'quadratic' : 'line'
      },
      style: (data: EdgeData) => {
        const d = data.data as { curveOffset?: number } | undefined
        return {
          stroke: isNeo ? '#94a3b8' : '#cbd5e1',
          lineWidth: 1,
          endArrow: true,
          curveOffset: d?.curveOffset ?? 0,
          curvePosition: 0.5,
        }
      },
      state: {
        active: { stroke: isNeo ? '#6366f1' : '#2563eb', lineWidth: 2 },
      },
    },
    behaviors: ['drag-canvas', 'drag-element', 'zoom-canvas', 'optimize-viewport-transform'],
  })

  afterLayoutFitHandler = () => {
    try {
      void graph?.fitView(undefined, false)
    } catch {
      /* noop */
    }
  }
  graph.on(GraphEvent.AFTER_LAYOUT, afterLayoutFitHandler)

  unbindInteractions = bindGraphInteractions(graph)

  try {
    await graph.render()
    await graph.fitView(undefined, false)
  } catch (err) {
    console.warn('[GraphView] render failed', err)
  }

  bindResize(el)
}

async function applyLayoutSwitch() {
  if (!graph || graph.destroyed) return
  const data = graph.getData()
  const nodes = data.nodes
  const nCount = nodes.length
  if (nCount === 0) return
  const nodeSizeFn = buildNodeSizeFn()
  const focusId = (nodes[0] as NodeData).id ? String((nodes[0] as NodeData).id) : null
  const layout = resolveLayout(activeLayout.value, nCount, nodeSizeFn, focusId)
  try {
    graph.setLayout(layout)
    await graph.layout()
    await graph.fitView(undefined, false)
    lastSignature = ''
  } catch (err) {
    console.warn('[GraphView] layout switch failed', err)
  }
}

const showNeo4jEmpty = computed(() => {
  if (props.variant !== 'neo4j' || props.loading) return false
  const d = props.neo4jData
  if (d == null) return true
  return d.nodes.length === 0 && d.edges.length === 0
})

onMounted(() => {
  void mountGraph()
})

watch(
  () => [
    props.variant,
    props.neo4jData,
    props.totalNodes,
    props.initialCap,
    props.maxNeoNodes,
    props.loading,
  ],
  () => {
    void mountGraph()
  },
  { deep: true },
)

watch(activeLayout, () => {
  void applyLayoutSwitch()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  destroyGraph()
  lastSignature = ''
})
</script>

<template>
  <div class="graph-wrap">
    <div v-if="showHeading" class="graph-title">关系图（G6 · 专业布局与交互）</div>
    <p v-if="showHeading" class="graph-meta">
      数据来自 Neo4j（前端最多展示 {{ maxNeoNodes }} 个节点）。
    </p>

    <div v-if="!showNeo4jEmpty && !loading" class="graph-toolbar">
      <span class="toolbar-label">布局</span>
      <el-radio-group v-model="activeLayout" size="small">
        <el-radio-button value="force">力导向</el-radio-button>
        <el-radio-button value="dagre">层次</el-radio-button>
        <el-radio-button value="radial">辐射</el-radio-button>
      </el-radio-group>
    </div>

    <div class="graph-canvas-wrap" v-loading="loading">
      <el-empty
        v-if="showNeo4jEmpty"
        description="暂无关系数据。可由管理员调用 POST /graph/node、POST /graph/edge 写入 Neo4j，或直接在 Browser 中建点边后刷新本页。"
      />
      <div v-show="!showNeo4jEmpty" ref="containerRef" class="graph-canvas" />
    </div>
    <p class="graph-hint">拖拽画布与节点、滚轮缩放；悬停高亮节点与关联边；点击节点可接业务线索。</p>
  </div>
</template>

<style scoped>
.graph-wrap {
  margin-top: 16px;
}

.graph-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.graph-meta {
  font-size: 12px;
  color: #4b5563;
  margin: 0 0 8px;
}

.graph-meta code {
  font-size: 11px;
}

.graph-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 12px;
  color: #6b7280;
}

.graph-canvas-wrap {
  min-height: 500px;
  position: relative;
  width: 100%;
}

.graph-canvas {
  width: 100%;
  min-height: 500px;
  height: 62vh;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fafafa;
}

.graph-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}
</style>
