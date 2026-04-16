/**
 * 图谱交互状态：选中节点、布局模式、子图上下文（不含 G6 实例，避免内存泄漏）。
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
  /** 当前视窗内快照（由页面在 render 后写入，可选） */
  const viewportMeta = ref<Record<string, unknown> | null>(null)
  /** 最近一次从服务端拉取的子图（只读缓存，非权威数据源） */
  const lastGraphPayload = ref<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null)

  const hasSelection = computed(
    () => selectedNodeId.value !== null || selectedEdgeId.value !== null,
  )

  function bindCase(id: number | null) {
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
    lastGraphPayload.value = payload
  }

  function resetForCaseSwitch() {
    selectedNodeId.value = null
    selectedEdgeId.value = null
    viewportMeta.value = null
    lastGraphPayload.value = null
  }

  return {
    caseId,
    layoutMode,
    selectedNodeId,
    selectedEdgeId,
    viewportMeta,
    lastGraphPayload,
    hasSelection,
    bindCase,
    setLayoutMode,
    selectNode,
    selectEdge,
    setLastGraphPayload,
    resetForCaseSwitch,
  }
})
