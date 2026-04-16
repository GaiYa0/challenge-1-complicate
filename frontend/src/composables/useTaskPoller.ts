/**
 * 任务轮询（批量 + 退避 + 去抖）。
 *
 * 设计：
 * - 单次 tick 只发 1 个 POST /task/batch 请求，覆盖所有未完成 id（≤64 个）。
 * - 429 / 网络错误使用指数退避（最大 20s），避免与限流器抖动共振。
 * - 完成 / 失败去重累计，全部终态后立即停止并回调。
 * - 组件卸载时 `onBeforeUnmount` 停止轮询。
 */
import { ref, computed, watch, onBeforeUnmount, type Ref } from 'vue'
import { getTasksBatch, type TaskBatchItem } from '../api/task'

interface UseTaskPollerOptions {
  taskIds: Ref<string[]>
  intervalMs?: number
  onAllComplete?: (results: Map<string, unknown>) => void
  /** 每批最多 id 数（与后端一致，默认 64） */
  batchSize?: number
  /** 最大退避，单位毫秒 */
  maxBackoffMs?: number
}

const TERMINAL_STATES = new Set(['SUCCESS', 'FAILURE', 'REVOKED', 'UNAUTHORIZED'])

export function useTaskPoller(options: UseTaskPollerOptions) {
  const {
    taskIds,
    intervalMs = 2500,
    onAllComplete,
    batchSize = 64,
    maxBackoffMs = 20_000,
  } = options

  const isPolling = ref(false)
  const completed = ref<Set<string>>(new Set())
  const failed = ref<Set<string>>(new Set())
  const results = ref<Map<string, unknown>>(new Map())

  let timer: ReturnType<typeof setTimeout> | null = null
  let consecutiveErrors = 0
  let stopped = false
  let inFlight = false

  const totalCount = computed(() => taskIds.value.length)
  const completedCount = computed(() => completed.value.size + failed.value.size)
  const progress = computed(() =>
    totalCount.value === 0 ? 0 : Math.round((completedCount.value / totalCount.value) * 100),
  )

  function currentPending(): string[] {
    return taskIds.value.filter(
      (id) => !completed.value.has(id) && !failed.value.has(id),
    )
  }

  function scheduleNext(delayMs: number) {
    if (stopped) return
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    timer = setTimeout(() => {
      void pollOnce()
    }, Math.max(250, delayMs))
  }

  function applyBatchItems(items: TaskBatchItem[]): void {
    if (!Array.isArray(items)) return
    const nextCompleted = new Set(completed.value)
    const nextFailed = new Set(failed.value)
    for (const item of items) {
      if (!item || typeof item.task_id !== 'string') continue
      const state = String(item.state || '').toUpperCase()
      if (state === 'SUCCESS') {
        nextCompleted.add(item.task_id)
        results.value.set(item.task_id, item.result ?? null)
      } else if (TERMINAL_STATES.has(state)) {
        nextFailed.add(item.task_id)
      }
    }
    completed.value = nextCompleted
    failed.value = nextFailed
  }

  async function pollOnce(): Promise<void> {
    if (stopped || inFlight) return
    const pending = currentPending()
    if (pending.length === 0) {
      stopInternal()
      onAllComplete?.(results.value)
      return
    }
    inFlight = true
    try {
      const slice = pending.slice(0, Math.max(1, Math.min(batchSize, 64)))
      const data = await getTasksBatch(slice, { skipGlobalLoading: true })
      applyBatchItems(data?.items ?? [])
      consecutiveErrors = 0

      if (currentPending().length === 0) {
        stopInternal()
        onAllComplete?.(results.value)
        return
      }
      scheduleNext(intervalMs)
    } catch {
      consecutiveErrors += 1
      const backoff = Math.min(
        maxBackoffMs,
        Math.round(intervalMs * Math.pow(1.8, Math.min(consecutiveErrors, 6))),
      )
      scheduleNext(backoff)
    } finally {
      inFlight = false
    }
  }

  function start() {
    if (isPolling.value) return
    stopped = false
    consecutiveErrors = 0
    completed.value = new Set()
    failed.value = new Set()
    results.value = new Map()
    isPolling.value = true
    scheduleNext(0)
  }

  function stopInternal() {
    stopped = true
    isPolling.value = false
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function stop() {
    stopInternal()
  }

  watch(taskIds, () => {
    if (isPolling.value) {
      stopInternal()
      start()
    }
  })

  onBeforeUnmount(stopInternal)

  return { isPolling, completedCount, totalCount, progress, results, start, stop }
}
