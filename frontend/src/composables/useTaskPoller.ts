import { ref, computed, watch, onBeforeUnmount, type Ref } from 'vue'
import { getTaskStatus, getTaskResult } from '../api/task'

interface UseTaskPollerOptions {
  taskIds: Ref<string[]>
  intervalMs?: number
  onAllComplete?: (results: Map<string, unknown>) => void
}

export function useTaskPoller(options: UseTaskPollerOptions) {
  const { taskIds, intervalMs = 2500, onAllComplete } = options

  const isPolling = ref(false)
  const completed = ref<Set<string>>(new Set())
  const failed = ref<Set<string>>(new Set())
  const results = ref<Map<string, unknown>>(new Map())
  let timer: ReturnType<typeof setInterval> | null = null

  const totalCount = computed(() => taskIds.value.length)
  const completedCount = computed(() => completed.value.size + failed.value.size)
  const progress = computed(() =>
    totalCount.value === 0 ? 0 : Math.round((completedCount.value / totalCount.value) * 100),
  )

  async function pollOnce() {
    const pending = taskIds.value.filter(
      (id) => !completed.value.has(id) && !failed.value.has(id),
    )
    if (pending.length === 0) {
      stop()
      onAllComplete?.(results.value)
      return
    }
    await Promise.allSettled(
      pending.map(async (taskId) => {
        try {
          const status = (await getTaskStatus(taskId)) as { state: string }
          if (status.state === 'SUCCESS') {
            const result = await getTaskResult(taskId)
            results.value.set(taskId, result)
            completed.value = new Set([...completed.value, taskId])
          } else if (status.state === 'FAILURE') {
            failed.value = new Set([...failed.value, taskId])
          }
        } catch {
          // ignore transient errors, retry next tick
        }
      }),
    )
    // Check again after this round
    const stillPending = taskIds.value.filter(
      (id) => !completed.value.has(id) && !failed.value.has(id),
    )
    if (stillPending.length === 0) {
      stop()
      onAllComplete?.(results.value)
    }
  }

  function start() {
    if (isPolling.value) return
    completed.value = new Set()
    failed.value = new Set()
    results.value = new Map()
    isPolling.value = true
    pollOnce()
    timer = setInterval(pollOnce, intervalMs)
  }

  function stop() {
    isPolling.value = false
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  watch(taskIds, () => {
    if (isPolling.value) {
      stop()
      start()
    }
  })

  onBeforeUnmount(stop)

  return { isPolling, completedCount, totalCount, progress, results, start, stop }
}
