/**
 * 图谱交互状态：选中节点、布局模式、子图上下文（不含 G6 实例，避免内存泄漏）。
 * 所有图谱数据按 caseId 隔离缓存。
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { GraphEdge, GraphNode } from '../../types/domain'

export type GraphLayoutMode = 'force' | 'dagre' | 'radial' | 'main'

export const useGraphStore = defineStore('graph', () => {
  const caseId = ref<number | null>(null)
  const layoutMode = ref<GraphLayoutMode>('force')
  const selectedNodeId = ref<string | null>(null)
  const selectedEdgeId = ref<string | null>(null)
  const viewportMeta = ref<Record<string, unknown> | null>(null)

  const graphCache = ref<Record<number, { nodes: GraphNode[]; edges: GraphEdge[] }>>({})

  const lastGraphPayload = computed(() => {
    if (caseId.value == null) return null
    return graphCache.value[caseId.value] ?? null
  })

  const hasSelection = computed(
    () => selectedNodeId.value !== null || selectedEdgeId.value !== null,
  )

  function bindCase(id: number | null) {
    if (caseId.value !== id) {
      selectedNodeId.value = null
      selectedEdgeId.value = null
      viewportMeta.value = null
    }
    caseId.value = id
  }

  function setLayoutMode(mode: GraphLayoutMode) {
    layoutMode.value = mode
  }

  function selectNode(id: string | null) {
    selectedNodeId.value = id
    if (id !== null) {
      selectedEdgeId.value = null
    }
  }

  function selectEdge(id: string | null) {
    selectedEdgeId.value = id
    if (id !== null) {
      selectedNodeId.value = null
    }
  }

  function setLastGraphPayload(payload: { nodes: GraphNode[]; edges: GraphEdge[] } | null) {
    if (caseId.value == null) return
    if (payload) {
      graphCache.value = { ...graphCache.value, [caseId.value]: payload }
    } else {
      const next = { ...graphCache.value }
      delete next[caseId.value]
      graphCache.value = next
    }
  }

  function resetForCaseSwitch() {
    selectedNodeId.value = null
    selectedEdgeId.value = null
    viewportMeta.value = null
  }

  function clearCacheForCase(id: number) {
    const next = { ...graphCache.value }
    delete next[id]
    graphCache.value = next
  }

  return {
    caseId,
    layoutMode,
    selectedNodeId,
    selectedEdgeId,
    viewportMeta,
    lastGraphPayload,
    graphCache,
    hasSelection,
    bindCase,
    setLayoutMode,
    selectNode,
    selectEdge,
    setLastGraphPayload,
    resetForCaseSwitch,
    clearCacheForCase,
  }
})
