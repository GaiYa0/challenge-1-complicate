import http from './request'

/** GET /graph/relations 单条（后端 GraphRelation 序列化为 from / to） */
export interface GraphTransferRelation {
  from: string
  to: string
}

/** GET /graph/degree */
export interface GraphOutDegreeRow {
  name: string
  degree: number
}

/** POST /graph/node（admin） */
export function createGraphUserNode(body: { name: string }) {
  return http.post('/graph/node', body)
}

/** POST /graph/edge（admin） */
export function createGraphEdge(body: { from_user: string; to_user: string }) {
  return http.post('/graph/edge', body)
}

/** GET /graph/relations（admin） */
export function listGraphTransferRelations() {
  return http.get('/graph/relations') as Promise<GraphTransferRelation[]>
}

/** GET /graph/degree（admin） */
export function listGraphOutDegree() {
  return http.get('/graph/degree') as Promise<GraphOutDegreeRow[]>
}

export interface GraphVisualizationNode {
  id: string
  label: string
}

export interface GraphVisualizationEdge {
  id: string
  source: string
  target: string
  /** 表格构图边权：金额合计或笔数（与后端 case 边一致） */
  weight?: number
}

export interface GraphVisualizationData {
  nodes: GraphVisualizationNode[]
  edges: GraphVisualizationEdge[]
}

/** 案件分析页：Neo4j User-[:TRANSFER]->User 子图（G6） */
export function getAnalysisGraph(caseId: number, edgeLimit = 100): Promise<GraphVisualizationData> {
  return http.get(`/cases/${caseId}/analysis/graph`, { params: { edge_limit: edgeLimit } }) as Promise<GraphVisualizationData>
}

export interface MergedGraphData {
  nodes: Record<string, unknown>[]
  edges: Record<string, unknown>[]
  case_ids: number[]
}

/** 跨案件合并图谱 */
export function getMergedCasesGraph(caseIds: number[], limit = 80): Promise<MergedGraphData> {
  return http.get('/cases/graph', {
    params: { case_ids: caseIds.join(','), limit },
  }) as Promise<MergedGraphData>
}
