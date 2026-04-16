import type { AxiosRequestConfig } from 'axios'
import http from './request'

export interface TaskEnqueueData {
  task_id: string
}

export interface TaskStatusData {
  state: string
}

export interface TaskResultData {
  state: string
  result: unknown
}

export interface TaskBatchItem {
  task_id: string
  state: string
  result?: unknown
  error?: string | null
}

export interface TaskBatchData {
  items: TaskBatchItem[]
}

/** GET /task/{task_id} → PENDING | STARTED | SUCCESS | FAILURE */
export function getTaskStatus(taskId: string, config?: AxiosRequestConfig) {
  return http.get(`/task/${encodeURIComponent(taskId)}`, config) as Promise<TaskStatusData>
}

/** GET /task/result/{task_id} */
export function getTaskResult(taskId: string, config?: AxiosRequestConfig) {
  return http.get(`/task/result/${encodeURIComponent(taskId)}`, config) as Promise<TaskResultData>
}

/** POST /task/batch — 一次拿多个任务状态+结果，避免轮询风暴 */
export function getTasksBatch(taskIds: string[], config?: AxiosRequestConfig) {
  const ids = Array.from(
    new Set(
      (taskIds ?? []).filter((t): t is string => typeof t === 'string' && t.length > 0),
    ),
  ).slice(0, 64)
  if (ids.length === 0) {
    return Promise.resolve<TaskBatchData>({ items: [] })
  }
  return http.post('/task/batch', { task_ids: ids }, config) as Promise<TaskBatchData>
}

/** 兼容旧接口：等价 basic 分析 */
export function enqueueLegacyAnalyze(filename: string) {
  return http.post(`/task/analyze/${encodeURIComponent(filename)}`) as Promise<TaskEnqueueData>
}
