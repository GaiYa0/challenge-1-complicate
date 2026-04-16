import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { listCases, createCase, updateCase, deleteCase } from '../api/case'
import type { CaseOut, CaseCreate } from '../api/case'

export const useCaseStore = defineStore('case', () => {
  const cases = ref<CaseOut[]>([])
  const currentCaseId = ref<number | null>(null)
  const loading = ref(false)

  const currentCase = computed(() =>
    cases.value.find((c) => c.id === currentCaseId.value) ?? null,
  )

  async function fetchCases() {
    loading.value = true
    try {
      const data = await listCases()
      cases.value = data as unknown as CaseOut[]
    } finally {
      loading.value = false
    }
  }

  async function addCase(body: CaseCreate): Promise<CaseOut> {
    const data = await createCase(body)
    const created = data as unknown as CaseOut
    cases.value.unshift(created)
    return created
  }

  async function removeCase(id: number) {
    await deleteCase(id)
    cases.value = cases.value.filter((c) => c.id !== id)
    if (currentCaseId.value === id) currentCaseId.value = null
  }

  async function completeCase(id: number) {
    const data = await updateCase(id, { status: 'completed' })
    const updated = data as unknown as CaseOut
    const idx = cases.value.findIndex((c) => c.id === id)
    if (idx !== -1) cases.value[idx] = updated
  }

  function selectCase(id: number) {
    currentCaseId.value = id
  }

  // In-memory per-session analysis cache (keyed by caseId)
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

  return {
    cases,
    currentCaseId,
    currentCase,
    loading,
    fetchCases,
    addCase,
    removeCase,
    completeCase,
    selectCase,
    saveAnalysis,
    getAnalysis,
    saveRisk,
    getRisk,
  }
})
