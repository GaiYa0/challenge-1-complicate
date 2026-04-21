import type { AxiosRequestConfig } from 'axios'
import http from './request'

export interface ClueListItem {
  id: number
  title: string
  risk_level: string
  risk_score: number
  category?: string
}

export interface ClueDetail {
  id: number
  case_id: number
  person_id: string
  title: string
  summary: string | null
  category: string
  risk_level: string
  risk_score: number
  rule_hits: unknown[]
  feature_snapshot: Record<string, unknown>
  risk_prompts: unknown[]
  created_at: string
  updated_at: string
}

/** GET /cases/{case_id}/persons/{person_id}/clues */
export function listPersonClues(caseId: number, personId: string) {
  return http.get(`/cases/${caseId}/persons/${encodeURIComponent(personId)}/clues`) as Promise<ClueListItem[]>
}

/** GET /api/clues/{clue_id}（axios baseURL 含 /api，此处为 `/clues/{id}`） */
export function getClueDetail(clueId: number, config?: AxiosRequestConfig) {
  return http.get(`/clues/${clueId}`, {
    ...config,
    skipGlobalLoading: config?.skipGlobalLoading ?? true,
  }) as Promise<ClueDetail>
}
