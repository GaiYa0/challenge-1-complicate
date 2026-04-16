/**
 * 关系分析闭环：主图 → 人物 → 线索列表 → 同心圆 → 线索详情侧栏。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import type { ClueDetail, ClueListItem } from '../../api/clue'
import {
  fetchAnalysisGraph,
  fetchClueDetail,
  fetchGraphOutDegree,
  fetchPersonClues,
} from '../../api/relationshipAnalysis'
import type { GraphOutDegreeRow, GraphVisualizationData } from '../../api/graph'

export type RelationshipViewMode = 'main' | 'clue'

function errText(e: unknown): string {
  return e instanceof Error ? e.message : '请求失败'
}

export const useRelationshipAnalysisStore = defineStore('relationshipAnalysis', () => {
  const caseId = ref<number | null>(null)
  const mode = ref<RelationshipViewMode>('main')

  const mainLoading = ref(false)
  const graphData = ref<GraphVisualizationData | null>(null)
  const graphError = ref<string | null>(null)
  const degreeList = ref<GraphOutDegreeRow[]>([])

  const cluesLoading = ref(false)
  const cluesError = ref<string | null>(null)
  const selectedPersonId = ref<string | null>(null)
  const selectedPersonLabel = ref('')
  const personClues = ref<ClueListItem[]>([])

  const selectedClueId = ref<number | null>(null)
  const clueDetail = ref<ClueDetail | null>(null)
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)

  const hasGraphNodes = computed(() => (graphData.value?.nodes?.length ?? 0) > 0)

  function resetClueFlow() {
    mode.value = 'main'
    cluesError.value = null
    cluesLoading.value = false
    selectedPersonId.value = null
    selectedPersonLabel.value = ''
    personClues.value = []
    clearClueDetail()
  }

  function clearClueDetail() {
    selectedClueId.value = null
    clueDetail.value = null
    detailError.value = null
    detailLoading.value = false
  }

  /** 切换案件或进入页时绑定 caseId，并清空线索态 */
  function bindCase(id: number) {
    caseId.value = id
    resetClueFlow()
    graphData.value = null
    degreeList.value = []
    graphError.value = null
  }

  /** 1. 加载主图 + 出度表 */
  async function loadMainGraph() {
    graphError.value = null
    mainLoading.value = true
    try {
      const [g, d] = await Promise.all([fetchAnalysisGraph(100), fetchGraphOutDegree()])
      graphData.value = g
      degreeList.value = [...d].sort((a, b) => b.degree - a.degree)
    } catch (e) {
      graphError.value = errText(e)
      graphData.value = null
      degreeList.value = []
      ElMessage.error(`加载关系图失败：${graphError.value}`)
    } finally {
      mainLoading.value = false
    }
  }

  /** 2–4. 点击人物 → 请求线索 → 切同心圆视图 */
  async function enterClueView(personId: string, personLabel: string) {
    const cid = caseId.value
    if (cid == null) return
    clearClueDetail()
    cluesError.value = null
    selectedPersonId.value = personId
    selectedPersonLabel.value = personLabel
    cluesLoading.value = true
    try {
      personClues.value = await fetchPersonClues(cid, personId)
      mode.value = 'clue'
    } catch (e) {
      cluesError.value = errText(e)
      personClues.value = []
      ElMessage.error(`加载线索失败：${cluesError.value}`)
      resetClueFlow()
    } finally {
      cluesLoading.value = false
    }
  }

  /** 5–6. 点击线索节点 → 侧栏详情 */
  async function selectClueForDetail(id: number) {
    selectedClueId.value = id
    clueDetail.value = null
    detailError.value = null
    detailLoading.value = true
    try {
      clueDetail.value = await fetchClueDetail(id)
    } catch (e) {
      detailError.value = errText(e)
      clueDetail.value = null
    } finally {
      detailLoading.value = false
    }
  }

  async function retryClueDetail() {
    const id = selectedClueId.value
    if (id == null) return
    await selectClueForDetail(id)
  }

  function exitClueView() {
    resetClueFlow()
  }

  return {
    caseId,
    mode,
    mainLoading,
    graphData,
    graphError,
    degreeList,
    cluesLoading,
    cluesError,
    selectedPersonId,
    selectedPersonLabel,
    personClues,
    selectedClueId,
    clueDetail,
    detailLoading,
    detailError,
    hasGraphNodes,
    bindCase,
    loadMainGraph,
    enterClueView,
    selectClueForDetail,
    clearClueDetail,
    retryClueDetail,
    exitClueView,
    resetClueFlow,
  }
})
