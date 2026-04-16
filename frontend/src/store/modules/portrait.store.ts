/**
 * 人物画像 Store：按 (caseId, personId) 缓存完整画像并暴露加载动作。
 *
 * 视图只订阅 state，严禁直连 api/portrait。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getPersonPortrait, type PersonPortrait } from '../../api/portrait'

function buildKey(caseId: number | null, personId: string): string {
  return `${Number(caseId ?? 0)}|${personId ?? ''}`
}

export const usePortraitStore = defineStore('portrait', () => {
  const cache = ref<Record<string, PersonPortrait>>({})
  const loading = ref(false)
  const lastError = ref<string | null>(null)
  const currentKey = ref<string>('')

  const current = computed<PersonPortrait | null>(() => {
    return currentKey.value ? cache.value[currentKey.value] ?? null : null
  })

  async function load(caseId: number, personId: string, opts?: { force?: boolean }): Promise<PersonPortrait | null> {
    if (!personId || !Number.isFinite(caseId)) {
      currentKey.value = ''
      return null
    }
    const key = buildKey(caseId, personId)
    currentKey.value = key
    const cached = cache.value[key]
    if (cached && !opts?.force) {
      return cached
    }
    loading.value = true
    lastError.value = null
    try {
      const data = await getPersonPortrait(caseId, personId)
      if (data) {
        cache.value = { ...cache.value, [key]: data }
      }
      return data ?? null
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      loading.value = false
    }
  }

  function reset() {
    cache.value = {}
    loading.value = false
    lastError.value = null
    currentKey.value = ''
  }

  return {
    loading,
    lastError,
    current,
    load,
    reset,
  }
})
