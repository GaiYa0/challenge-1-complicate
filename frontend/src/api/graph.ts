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
}

export interface GraphVisualizationData {
  nodes: GraphVisualizationNode[]
  edges: GraphVisualizationEdge[]
}

/** 分析页：Neo4j User-[:TRANSFER]->User 子图（G6） */
export function getAnalysisGraph(edgeLimit = 100): Promise<GraphVisualizationData> {
  return http.get('/analysis/graph', { params: { edge_limit: edgeLimit } }) as Promise<GraphVisualizationData>
}
