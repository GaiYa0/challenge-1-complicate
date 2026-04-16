import http from './request'

/** 与后端 FeedbackIn 对齐：须提供 is_correct 或 label 之一；前端统一传 is_correct */
export interface FeedbackSubmitBody {
  filename: string
  is_correct: boolean
  prediction?: number | null
  model_name?: string | null
  model_version?: string | null
  entity_id?: number | null
}

/** POST /feedback */
export function submitFeedback(body: FeedbackSubmitBody) {
  return http.post('/feedback', body)
}
