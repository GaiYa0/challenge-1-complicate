/**
 * 案件上下文：列表、当前选中案件、会话内缓存键（与路由 caseId 对齐）。
 * 持久化策略由上层决定；此处不绑定具体业务字段。
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { listCases, createCase, updateCase, deleteCase, patchCase } from '../../api/case'
import type { CaseOut, CaseCreate } from '../../api/case'

export const useCaseStore = defineStore('case', () => {
  const cases = ref<CaseOut[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(24)
  const currentCaseId = ref<number | null>(null)
  const loading = ref(false)

  const currentCase = computed(() =>
    cases.value.find((c) => c.id === currentCaseId.value) ?? null,
  )

  async function fetchCases(nextPage?: number) {
    if (nextPage != null) page.value = nextPage
    loading.value = true
    try {
      const data = await listCases({
        page: page.value,
        page_size: pageSize.value,
      })
      cases.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function addCase(body: CaseCreate): Promise<CaseOut> {
    const data = await createCase(body)
    const created = data as unknown as CaseOut
    await fetchCases(1)
    return created
  }

  async function removeCase(id: number) {
    await deleteCase(id)
    if (currentCaseId.value === id) {
      currentCaseId.value = null
    }
    await fetchCases(page.value)
  }

  async function completeCase(id: number) {
    const data = await updateCase(id, { status: 'completed' })
    const updated = data as unknown as CaseOut
    const idx = cases.value.findIndex((c) => c.id === id)
    if (idx !== -1) cases.value[idx] = updated
  }

  async function renameCase(id: number, newName: string): Promise<CaseOut> {
    const data = await patchCase(id, { name: newName })
    const updated = data as unknown as CaseOut
    const idx = cases.value.findIndex((c) => c.id === id)
    if (idx !== -1) cases.value[idx] = updated
    return updated
  }

  function selectCase(id: number) {
    currentCaseId.value = id
  }

  const analysisCache = ref<Record<number, Record<string, unknown>>>({})
  const riskCache = ref<Record<number, Record<string, unknown>>>({})

  function saveAnalysis(caseId: number, data: Record<string, unknown>) {
    analysisCache.value[caseId] = data
  }

  function getAnalysis(caseId: number): Record<string, unknown> | null {
    return analysisCache.value[caseId] ?? null
  }

  function saveRisk(caseId: number, data: Record<string, unknown>) {
    riskCache.value[caseId] = data
  }

  function getRisk(caseId: number): Record<string, unknown> | null {
    return riskCache.value[caseId] ?? null
  }

  function clearSessionCachesForCase(caseId: number) {
    delete analysisCache.value[caseId]
    delete riskCache.value[caseId]
  }

  return {
    cases,
    total,
    page,
    pageSize,
    currentCaseId,
    currentCase,
    loading,
    fetchCases,
    addCase,
    removeCase,
    completeCase,
    renameCase,
    selectCase,
    saveAnalysis,
    getAnalysis,
    saveRisk,
    getRisk,
    clearSessionCachesForCase,
  }
})
