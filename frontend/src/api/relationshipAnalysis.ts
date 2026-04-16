/**
 * 关系网络页闭环：主图、人物线索、线索详情。
 * 统一 skipGlobalLoading：由页面/store 控制骨架与局部 loading，避免与全局请求计数叠加。
 * 统一 silentError：由 store 统一提示与错误态。
 */
import type { AxiosRequestConfig } from 'axios'
import http from './request'
import type { ClueDetail, ClueListItem } from './clue'
import type { GraphOutDegreeRow, GraphVisualizationData } from './graph'

const silent: AxiosRequestConfig = {
  skipGlobalLoading: true,
  silentError: true,
}

/** GET /api/analysis/graph（边条数上限与后端裁剪配合，控制节点规模） */
export function fetchAnalysisGraph(edgeLimit = 100): Promise<GraphVisualizationData> {
  return http.get('/analysis/graph', {
    ...silent,
    params: { edge_limit: edgeLimit },
  }) as Promise<GraphVisualizationData>
}

/** GET /api/analysis/degree（普通用户可读，与关系网络页一致） */
export function fetchGraphOutDegree(): Promise<GraphOutDegreeRow[]> {
  return http.get('/analysis/degree', silent) as Promise<GraphOutDegreeRow[]>
}

/** GET /api/cases/{case_id}/persons/{person_id}/clues */
export function fetchPersonClues(caseId: number, personId: string): Promise<ClueListItem[]> {
  return http.get(`/cases/${caseId}/persons/${encodeURIComponent(personId)}/clues`, silent) as Promise<
    ClueListItem[]
  >
}

/** GET /api/clues/{clue_id} */
export function fetchClueDetail(clueId: number): Promise<ClueDetail> {
  return http.get(`/clues/${clueId}`, silent) as Promise<ClueDetail>
}
