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

/** GET /task/{task_id} → PENDING | STARTED | SUCCESS | FAILURE */
export function getTaskStatus(taskId: string, config?: AxiosRequestConfig) {
  return http.get(`/task/${encodeURIComponent(taskId)}`, config) as Promise<TaskStatusData>
}

/** GET /task/result/{task_id} */
export function getTaskResult(taskId: string, config?: AxiosRequestConfig) {
  return http.get(`/task/result/${encodeURIComponent(taskId)}`, config) as Promise<TaskResultData>
}

/** 兼容旧接口：等价 basic 分析 */
export function enqueueLegacyAnalyze(filename: string) {
  return http.post(`/task/analyze/${encodeURIComponent(filename)}`) as Promise<TaskEnqueueData>
}
