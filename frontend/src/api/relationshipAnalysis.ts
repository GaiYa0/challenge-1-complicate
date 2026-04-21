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

function withSilent(extra?: AxiosRequestConfig): AxiosRequestConfig {
  if (!extra) return silent
  return { ...silent, ...extra }
}

/** GET /api/cases/{caseId}/analysis/graph */
export function fetchAnalysisGraph(
  caseId: number,
  edgeLimit = 100,
  config?: AxiosRequestConfig,
): Promise<GraphVisualizationData> {
  return http.get(`/cases/${caseId}/analysis/graph`, {
    ...withSilent(config),
    params: { edge_limit: edgeLimit, ...(config?.params ?? {}) },
  }) as Promise<GraphVisualizationData>
}

/** GET /api/cases/{caseId}/analysis/degree */
export function fetchGraphOutDegree(
  caseId: number,
  config?: AxiosRequestConfig,
): Promise<GraphOutDegreeRow[]> {
  return http.get(`/cases/${caseId}/analysis/degree`, withSilent(config)) as Promise<GraphOutDegreeRow[]>
}

/** GET /api/cases/{case_id}/persons/{person_id}/clues */
export function fetchPersonClues(
  caseId: number,
  personId: string,
  config?: AxiosRequestConfig,
): Promise<ClueListItem[]> {
  return http.get(
    `/cases/${caseId}/persons/${encodeURIComponent(personId)}/clues`,
    withSilent(config),
  ) as Promise<ClueListItem[]>
}

/** GET /api/clues/{clue_id} */
export function fetchClueDetail(
  clueId: number,
  config?: AxiosRequestConfig,
): Promise<ClueDetail> {
  return http.get(`/clues/${clueId}`, withSilent(config)) as Promise<ClueDetail>
}
