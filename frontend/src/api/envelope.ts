/**
 * 与后端 UnifiedResponse 对齐的契约与工具函数。
 */

export interface ApiEnvelope<T = unknown> {
  code: number
  msg: string
  data: T | null
  request_id?: string
}

export function isApiEnvelope(v: unknown): v is ApiEnvelope {
  return (
    typeof v === 'object' &&
    v !== null &&
    'code' in v &&
    typeof (v as ApiEnvelope).code === 'number' &&
    'msg' in v &&
    typeof (v as ApiEnvelope).msg === 'string'
  )
}

export function extractRequestId(body: unknown): string | undefined {
  if (isApiEnvelope(body) && body.request_id) {
    return body.request_id
  }
  return undefined
}
