/**
 * 分析编排 Store：聚合「开始分析 / 汇总概况」两个用例。
 *
 * 视图层仅允许调用本 store 暴露的 actions 与只读 state；
 * 所有文件/分析/异常/清洗接口都集中在这里调度，杜绝视图直连 api。
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

import { enqueueAnalyzeJob, type AnalyzeJobKind } from '../../api/analyze'
import {
  getFileAnomaly,
  getFilePreview,
  listDbFiles,
  type AnomalyData,
  type FileDetailItem,
  type PreviewData,
} from '../../api/file'

export interface AnalysisSummary {
  dataOverview: { rows: number; cols: number } | null
  anomalyCount: number | null
  cleanBefore: number | null
  cleanAfter: number | null
}

const EMPTY_SUMMARY: AnalysisSummary = {
  dataOverview: null,
  anomalyCount: null,
  cleanBefore: null,
  cleanAfter: null,
}

const DEFAULT_KINDS: ReadonlyArray<AnalyzeJobKind> = [
  'basic',
  'iforest',
  'graph',
  'clean',
]

/**
 * clean / feature 任务会在 DB 中插入形如 `clean_<hash>_<orig>` 的派生文件；
 * 若下次「开始分析」不过滤，派生文件会再次进入流水线，产生
 * `clean_<hash2>_clean_<hash1>_<orig>` 的指数级膨胀 → 触发限流。
 */
const DERIVATIVE_PREFIXES: ReadonlyArray<string> = ['clean_', 'feature_']

function isDerivativeFilename(name: string): boolean {
  return DERIVATIVE_PREFIXES.some((p) => name.startsWith(p))
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)))
}

export const useAnalysisStore = defineStore('analysis', () => {
  const files = ref<string[]>([])
  const filesLoading = ref(false)
  const filesError = ref<string | null>(null)
  const currentDataset = ref<string | null>(null)

  const enqueueing = ref(false)
  const enqueuedTaskIds = ref<string[]>([])

  const summary = ref<AnalysisSummary>({ ...EMPTY_SUMMARY })
  const summaryLoading = ref(false)

  const hasFiles = computed(() => files.value.length > 0)

  /**
   * @param dataset - 按 dataset 过滤（如 `case-123`），null/undefined 不过滤
   */
  async function fetchFiles(dataset?: string | null): Promise<string[]> {
    filesLoading.value = true
    filesError.value = null
    currentDataset.value = dataset ?? null
    try {
      const rows = (await listDbFiles()) as FileDetailItem[]
      let filtered = Array.isArray(rows) ? rows : []
      if (dataset) {
        filtered = filtered.filter((r) => r?.dataset === dataset)
      }
      const names = filtered
        .map((r) => r?.filename)
        .filter((s): s is string => typeof s === 'string')
      files.value = names
      return names
    } catch (e) {
      files.value = []
      filesError.value = e instanceof Error ? e.message : String(e)
      return []
    } finally {
      filesLoading.value = false
    }
  }

  async function enqueueAllAnalyses(
    kinds: ReadonlyArray<AnalyzeJobKind> = DEFAULT_KINDS,
  ): Promise<string[]> {
    const sources = files.value.filter(
      (n): n is string => typeof n === 'string' && n.length > 0 && !isDerivativeFilename(n),
    )
    if (sources.length === 0) {
      enqueuedTaskIds.value = []
      return []
    }
    enqueueing.value = true
    const ids: string[] = []
    const pacingMs = Math.max(60, Math.round(650 / Math.max(1, kinds.length)))
    try {
      for (const filename of sources) {
        for (const kind of kinds) {
          try {
            const res = await enqueueAnalyzeJob(kind, filename, currentDataset.value ?? undefined)
            const tid = typeof res?.task_id === 'string' ? res.task_id : ''
            if (tid) ids.push(tid)
          } catch (e) {
            console.warn('[analysis.store] enqueue failed', kind, filename, e)
          }
          await sleep(pacingMs)
        }
      }
      enqueuedTaskIds.value = ids
      return ids
    } finally {
      enqueueing.value = false
    }
  }

  async function loadSummary(filename?: string): Promise<AnalysisSummary> {
    const name = filename ?? files.value[0]
    if (!name) {
      summary.value = { ...EMPTY_SUMMARY }
      return summary.value
    }
    summaryLoading.value = true
    try {
      const [previewRes, anomalyRes] = await Promise.allSettled([
        getFilePreview(name),
        getFileAnomaly(name),
      ])
      const next: AnalysisSummary = { ...EMPTY_SUMMARY }
      if (previewRes.status === 'fulfilled') {
        const p = previewRes.value as PreviewData | undefined
        const shape = Array.isArray(p?.shape) ? p.shape : []
        const rows = Number(shape[0])
        const cols = Number(shape[1])
        if (Number.isFinite(rows) && Number.isFinite(cols)) {
          next.dataOverview = { rows, cols }
        }
      }
      if (anomalyRes.status === 'fulfilled') {
        const a = anomalyRes.value as AnomalyData | undefined
        const count = Number(a?.anomaly_count)
        next.anomalyCount = Number.isFinite(count) ? count : null
      }
      summary.value = next
      return next
    } finally {
      summaryLoading.value = false
    }
  }

  function applyCachedSummary(input: unknown): AnalysisSummary {
    const obj = (input ?? {}) as Partial<AnalysisSummary>
    const next: AnalysisSummary = {
      dataOverview: obj.dataOverview ?? null,
      anomalyCount:
        typeof obj.anomalyCount === 'number' && Number.isFinite(obj.anomalyCount)
          ? obj.anomalyCount
          : null,
      cleanBefore:
        typeof obj.cleanBefore === 'number' && Number.isFinite(obj.cleanBefore)
          ? obj.cleanBefore
          : null,
      cleanAfter:
        typeof obj.cleanAfter === 'number' && Number.isFinite(obj.cleanAfter)
          ? obj.cleanAfter
          : null,
    }
    summary.value = next
    return next
  }

  function reset() {
    files.value = []
    filesLoading.value = false
    filesError.value = null
    currentDataset.value = null
    enqueueing.value = false
    enqueuedTaskIds.value = []
    summary.value = { ...EMPTY_SUMMARY }
    summaryLoading.value = false
  }

  return {
    files,
    filesLoading,
    filesError,
    enqueueing,
    enqueuedTaskIds,
    summary,
    summaryLoading,
    hasFiles,
    fetchFiles,
    enqueueAllAnalyses,
    loadSummary,
    applyCachedSummary,
    reset,
  }
})
