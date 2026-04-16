<script setup lang="ts">
import { Graph, NodeEvent } from '@antv/g6'
import type { IEvent, IPointerEvent, Node as G6Node } from '@antv/g6'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ClueListItem } from '../../api/clue'
import { useRelationshipAnalysisStore } from '../../store/modules/relationshipAnalysis.store'
import ClueDetailPanel from '../investigation/ClueDetailPanel.vue'
import {
  CLUE_CENTER_ID,
  CLUE_RING_RADII,
  cluesToGraphData,
} from '../../utils/clueConcentricLayout'

const props = withDefaults(
  defineProps<{
    personId: string
    personLabel: string
    clues: ClueListItem[]
    loading?: boolean
  }>(),
  { loading: false },
)

const emit = defineEmits<{
  (e: 'back'): void
}>()

const ra = useRelationshipAnalysisStore()

const containerRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null
let resizeObserver: ResizeObserver | null = null

function getCanvasSize(el: HTMLDivElement): [number, number] {
  const w = Math.max(1, Math.floor(el.clientWidth || el.getBoundingClientRect().width))
  const hRaw = el.clientHeight || el.getBoundingClientRect().height
  const h = Math.max(500, Math.floor(hRaw > 0 ? hRaw : 500))
  return [w, h]
}

function nodeIdFromPointer(evt: IEvent): string | null {
  const e = evt as IPointerEvent<G6Node>
  if (e.targetType !== 'node' || !e.target) return null
  const raw = (e.target as unknown as { id?: string | number }).id
  return raw != null ? String(raw) : null
}

function bindGraphInteractions(g: Graph) {
  const onClick = (evt: IEvent) => {
    const id = nodeIdFromPointer(evt)
    if (!id || !g.hasNode(id) || id === CLUE_CENTER_ID) return
    const data = g.getNodeData(id)
    const raw = data.data as { kind?: string; clueId?: number } | undefined
    if (raw?.kind !== 'clue' || raw.clueId == null) return
    void ra.selectClueForDetail(raw.clueId)
  }
  g.on(NodeEvent.CLICK, onClick)
  return () => {
    g.off(NodeEvent.CLICK, onClick)
  }
}

let unbind: (() => void) | null = null

async function mountGraph() {
  resizeObserver?.disconnect()
  resizeObserver = null
  unbind?.()
  unbind = null
  graph?.destroy()
  graph = null

  if (props.loading) return
  const el = containerRef.value
  if (!el) return

  const [width, height] = getCanvasSize(el)
  const cx = width / 2
  const cy = height / 2
  const { nodes, edges } = cluesToGraphData(cx, cy, props.personLabel, props.clues)

  graph = new Graph({
    container: el,
    width,
    height,
    data: { nodes, edges },
    edge: {
      type: 'line',
      style: {
        stroke: '#94a3b8',
        lineWidth: 1,
        lineDash: [4, 4],
        opacity: 0.55,
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'optimize-viewport-transform'],
  })

  unbind = bindGraphInteractions(graph)

  await graph.render()
  await graph.fitView({ when: 'always' }, false)

  const ro = new ResizeObserver(() => {
    if (!graph) return
    const [w, h] = getCanvasSize(el)
    graph.resize(w, h)
    const ncx = w / 2
    const ncy = h / 2
    const next = cluesToGraphData(ncx, ncy, props.personLabel, props.clues)
    graph.setData({ nodes: next.nodes, edges: next.edges })
    void graph.render().then(() => graph?.fitView({ when: 'always' }, false))
  })
  ro.observe(el)
  resizeObserver = ro
}

onMounted(() => {
  void mountGraph()
})

watch(
  () => [props.clues, props.personLabel, props.loading, props.personId] as const,
  () => {
    ra.clearClueDetail()
    void mountGraph()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  unbind?.()
  unbind = null
  graph?.destroy()
  graph = null
})
</script>

<template>
  <div class="clue-graph-wrap">
    <div class="clue-toolbar">
      <el-button type="primary" plain @click="emit('back')">
        &larr; 返回关系图
      </el-button>
      <div class="clue-toolbar-meta">
        <span class="name">{{ personLabel }}</span>
        <span class="hint">同心圆线索 · 内→外：高 / 中 / 低风险（半径 {{ CLUE_RING_RADII.high }} / {{ CLUE_RING_RADII.medium }} / {{ CLUE_RING_RADII.low }} px）</span>
      </div>
    </div>

    <div class="clue-body">
      <div class="clue-main">
        <div class="clue-canvas-wrap" v-loading="loading">
          <div ref="containerRef" class="clue-canvas" />
        </div>
      </div>
      <ClueDetailPanel
        :clue-id="ra.selectedClueId"
        :detail="ra.clueDetail"
        :loading="ra.detailLoading"
        :error="ra.detailError"
        @close="ra.clearClueDetail()"
        @retry="ra.retryClueDetail()"
      />
    </div>
  </div>
</template>

<style scoped>
.clue-graph-wrap {
  width: 100%;
}

.clue-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.clue-toolbar-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  color: var(--app-text-secondary, #64748b);
}

.clue-toolbar-meta .name {
  font-weight: 600;
  font-size: 15px;
  color: var(--app-text, #0f172a);
}

.clue-toolbar-meta .hint {
  font-size: 12px;
}

.clue-body {
  display: flex;
  align-items: stretch;
  width: 100%;
  min-height: 500px;
}

.clue-main {
  flex: 1;
  min-width: 0;
}

.clue-canvas-wrap {
  position: relative;
  min-height: 500px;
}

.clue-canvas {
  width: 100%;
  min-height: 500px;
  height: 56vh;
  border: 1px solid var(--app-border, #e5e7eb);
  border-radius: var(--app-radius, 8px);
  background: radial-gradient(circle at 50% 50%, #f8fafc 0%, #f1f5f9 55%, #e2e8f0 100%);
}
</style>
