<script setup lang="ts">
import { Graph } from '@antv/g6'
import type { EdgeData, NodeData } from '@antv/g6'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { buildLineGraphData, clipGraphData } from '../../utils/graphSample'

export type Neo4jGraphPayload = {
  nodes: { id: string; label: string }[]
  edges: { id: string; source: string; target: string }[]
}

const props = withDefaults(
  defineProps<{
    /** demo：内置链；neo4j：使用 neo4jData（来自 /analysis/graph） */
    variant?: 'demo' | 'neo4j'
    /** variant=neo4j 时注入；null 表示尚未拉取完成 */
    neo4jData?: Neo4jGraphPayload | null
    loading?: boolean
    totalNodes?: number
    initialCap?: number
    showHeading?: boolean
  }>(),
  {
    variant: 'demo',
    neo4jData: null,
    loading: false,
    totalNodes: 48,
    initialCap: 48,
    showHeading: true,
  },
)

const containerRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null
let resizeObserver: ResizeObserver | null = null

/** Neo4j 模式且（加载中 / 无数据）时展示空状态，不画演示链 */
const showNeo4jEmpty = computed(() => {
  if (props.variant !== 'neo4j' || props.loading) return false
  const d = props.neo4jData
  if (d == null) return true
  return d.nodes.length === 0 && d.edges.length === 0
})

function mountGraph() {
  graph?.destroy()
  graph = null

  if (props.loading) return

  if (props.variant === 'neo4j') {
    const d = props.neo4jData
    if (!d || (d.nodes.length === 0 && d.edges.length === 0)) return

    const el = containerRef.value
    if (!el) return

    const nodes: NodeData[] = d.nodes.map((n) => ({
      id: n.id,
      data: { label: n.label },
    }))
    const edges: EdgeData[] = d.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
    }))

    graph = new Graph({
      container: el,
      width: el.clientWidth || 600,
      height: 320,
      data: { nodes, edges },
      layout: {
        type: 'force',
        linkDistance: 80,
        nodeStrength: -200,
        edgeStrength: 0.6,
      },
      node: {
        style: (data: NodeData) => {
          const raw = data.data as { label?: string } | undefined
          return {
            size: 36,
            labelText: raw?.label != null ? String(raw.label) : String(data.id ?? ''),
          }
        },
      },
      edge: { type: 'line', style: { endArrow: true } },
      behaviors: ['drag-canvas', 'drag-element', 'zoom-canvas', 'optimize-viewport-transform'],
    })
    graph.render()
    bindResize(el)
    return
  }

  /* ---- demo ---- */
  const el = containerRef.value
  if (!el) return
  const raw = buildLineGraphData(Math.max(2, props.totalNodes))
  const { nodes, edges } = clipGraphData(raw.nodes, raw.edges, Math.max(2, props.initialCap))
  const n = nodes.length
  graph = new Graph({
    container: el,
    width: el.clientWidth || 600,
    height: 320,
    data: { nodes, edges },
    layout: {
      type: 'grid',
      cols: Math.min(12, Math.max(n, 1)),
      rows: Math.ceil(Math.max(n, 1) / 12),
    },
    node: {
      style: (data: NodeData) => ({
        size: 32,
        labelText: String(data.id),
      }),
    },
    edge: { type: 'line', style: { endArrow: true } },
    behaviors: ['drag-canvas', 'drag-element', 'zoom-canvas', 'optimize-viewport-transform'],
  })
  graph.render()
  bindResize(el)
}

function bindResize(el: HTMLDivElement) {
  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver((entries) => {
    const entry = entries[0]
    if (entry && graph) {
      const w = entry.contentRect.width
      if (w > 0) graph.resize(w, 320)
    }
  })
  resizeObserver.observe(el)
}

onMounted(() => {
  mountGraph()
})

watch(
  () => [
    props.variant,
    props.neo4jData,
    props.totalNodes,
    props.initialCap,
    props.loading,
  ],
  () => {
    mountGraph()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  graph?.destroy()
  graph = null
})
</script>

<template>
  <div class="graph-wrap">
    <div v-if="showHeading" class="graph-title">关系图（G6 · 限制首屏节点 + 视口变换优化）</div>
    <p v-if="showHeading" class="graph-meta">
      <template v-if="variant === 'demo'">
        逻辑节点 {{ totalNodes }}，首屏挂载 {{ Math.min(initialCap, totalNodes) }}。
      </template>
      <template v-else>
        数据来自 <code>/analysis/graph</code>：Neo4j 中 <code>User</code> 经 <code>TRANSFER</code> 指向 <code>User</code> 的边。
      </template>
    </p>
    <div class="graph-canvas-wrap" v-loading="loading">
      <el-empty
        v-if="showNeo4jEmpty"
        description="暂无关系数据。可由管理员调用 POST /graph/node、POST /graph/edge 写入 Neo4j，或直接在 Browser 中建点边后刷新本页。"
      />
      <div v-show="!showNeo4jEmpty" ref="containerRef" class="graph-canvas" />
    </div>
    <p class="graph-hint">拖拽节点、滚轮缩放；节点多时依赖裁剪与 optimize-viewport-transform 减压。</p>
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

.graph-canvas-wrap {
  min-height: 320px;
  position: relative;
}

.graph-canvas {
  width: 100%;
  height: 320px;
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
