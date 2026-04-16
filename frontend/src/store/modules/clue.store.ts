/**
 * 线索列表与当前选中（服务端为权威；此处做列表缓存 / UI 选中态 / 详情缓存）。
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

import { getClueDetail, type ClueDetail } from '../../api/clue'
import type { Clue } from '../../types/domain'

export const useClueStore = defineStore('clue', () => {
  const caseId = ref<number | null>(null)
  const cluesByCaseId = ref<Record<number, Clue[]>>({})
  const selectedClueId = ref<number | null>(null)
  const loading = ref(false)

  const detailById = ref<Record<number, ClueDetail>>({})
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)
  const currentDetailId = ref<number | null>(null)

  const selectedClue = computed(() => {
    const cid = caseId.value
    const id = selectedClueId.value
    if (cid === null || id === null) return null
    const list = cluesByCaseId.value[cid] ?? []
    return list.find((c) => c.id === id) ?? null
  })

  const currentDetail = computed<ClueDetail | null>(() => {
    const id = currentDetailId.value
    return id !== null ? detailById.value[id] ?? null : null
  })

  function bindCase(id: number | null) {
    caseId.value = id
  }

  function setCluesForCase(cid: number, list: Clue[]) {
    cluesByCaseId.value = { ...cluesByCaseId.value, [cid]: list }
  }

  function selectClue(id: number | null) {
    selectedClueId.value = id
  }

  function clearForCase(cid: number) {
    const next = { ...cluesByCaseId.value }
    delete next[cid]
    cluesByCaseId.value = next
    if (caseId.value === cid) {
      selectedClueId.value = null
    }
  }

  async function fetchDetail(clueId: number, opts?: { force?: boolean }): Promise<ClueDetail | null> {
    if (!Number.isFinite(clueId)) return null
    currentDetailId.value = clueId
    const cached = detailById.value[clueId]
    if (cached && !opts?.force) return cached
    detailLoading.value = true
    detailError.value = null
    try {
      const data = await getClueDetail(clueId)
      if (data) {
        detailById.value = { ...detailById.value, [clueId]: data }
      }
      return data ?? null
    } catch (e) {
      detailError.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      detailLoading.value = false
    }
  }

  function reset() {
    caseId.value = null
    cluesByCaseId.value = {}
    selectedClueId.value = null
    loading.value = false
    detailById.value = {}
    detailLoading.value = false
    detailError.value = null
    currentDetailId.value = null
  }

  return {
    caseId,
    cluesByCaseId,
    selectedClueId,
    selectedClue,
    loading,
    detailById,
    detailLoading,
    detailError,
    currentDetailId,
    currentDetail,
    bindCase,
    setCluesForCase,
    selectClue,
    clearForCase,
    fetchDetail,
    reset,
  }
})
