import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAnalysisDashboard, type AnalysisDashboardData } from '../api/data'
import type { RealtimeMessage } from '../utils/websocket'

const MAX_LIVE_TREND_POINTS = 400

export const useDataStore = defineStore('data', () => {
  const analysisData = ref<AnalysisDashboardData | null>(null)
  const loading = ref(false)
  const liveScalar = ref<number | null>(null)

  let fetchInflight: Promise<void> | null = null

  async function fetchAnalysisData() {
    if (fetchInflight) return fetchInflight
    loading.value = true
    fetchInflight = (async () => {
      try {
        analysisData.value = await getAnalysisDashboard()
      } finally {
        loading.value = false
        fetchInflight = null
      }
    })()
    return fetchInflight
  }

  function applyRealtimeMessage(msg: RealtimeMessage) {
    if (msg.type === 'update' && msg.data && typeof msg.data === 'object' && 'value' in msg.data) {
      const v = Number((msg.data as { value: unknown }).value)
      if (!Number.isFinite(v)) {
        console.warn('[dataStore] update.value 非法', msg.data)
        return
      }
      liveScalar.value = v
      return
    }

    if (msg.type === 'trend_point' && msg.data && typeof msg.data === 'object') {
      const d = msg.data as { label?: unknown; value?: unknown }
      const label = String(d.label ?? '')
      const value = Number(d.value)
      if (!label || !Number.isFinite(value)) {
        console.warn('[dataStore] trend_point 字段非法', msg.data)
        return
      }
      const cur = analysisData.value
      if (!cur) return
      const labels = [...cur.trend_labels, label]
      const values = [...cur.trend_values, value]
      const overflow = Math.max(0, labels.length - MAX_LIVE_TREND_POINTS)
      analysisData.value = {
        ...cur,
        trend_labels: labels.slice(overflow),
        trend_values: values.slice(overflow),
      }
    }
  }

  return {
    analysisData,
    loading,
    liveScalar,
    fetchAnalysisData,
    applyRealtimeMessage,
  }
})
