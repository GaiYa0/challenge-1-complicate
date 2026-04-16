/**
 * 异步任务：轮询句柄、活跃任务 id 集合（与 Celery / 后端 analysis_tasks 对齐）。
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { AnalysisTask } from '../../types/domain'

export const useTaskStore = defineStore('task', () => {
  const caseId = ref<number | null>(null)
  /** caseId -> 最近一次任务列表快照 */
  const tasksByCaseId = ref<Record<number, AnalysisTask[]>>({})
  /** 正在轮询的 celery / public_id */
  const activePollingIds = ref<Set<string>>(new Set())
  const loading = ref(false)

  const hasActivePolling = computed(() => activePollingIds.value.size > 0)

  function bindCase(id: number | null) {
    caseId.value = id
  }

  function setTasksForCase(cid: number, tasks: AnalysisTask[]) {
    tasksByCaseId.value = { ...tasksByCaseId.value, [cid]: tasks }
  }

  function registerPolling(taskKey: string) {
    const s = new Set(activePollingIds.value)
    s.add(taskKey)
    activePollingIds.value = s
  }

  function unregisterPolling(taskKey: string) {
    const s = new Set(activePollingIds.value)
    s.delete(taskKey)
    activePollingIds.value = s
  }

  function clearForCase(cid: number) {
    const next = { ...tasksByCaseId.value }
    delete next[cid]
    tasksByCaseId.value = next
  }

  return {
    caseId,
    tasksByCaseId,
    activePollingIds,
    loading,
    hasActivePolling,
    bindCase,
    setTasksForCase,
    registerPolling,
    unregisterPolling,
    clearForCase,
  }
})
