import http from './request'
import type { TaskEnqueueData } from './task'

/** 与后端 analyze 路由一致；除 mock 外会校验文件归属 */
export type AnalyzeJobKind = 'mock' | 'basic' | 'iforest' | 'graph' | 'clean' | 'features'

function encFilename(name: string) {
  return encodeURIComponent(name)
}

/** POST /analyze/{kind}/{filename} */
export function enqueueAnalyzeJob(kind: AnalyzeJobKind, filename: string) {
  return http.post(`/analyze/${kind}/${encFilename(filename)}`) as Promise<TaskEnqueueData>
}
