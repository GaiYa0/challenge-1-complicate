import http from './request'

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
export function getAnalysisGraph(edgeLimit = 500): Promise<GraphVisualizationData> {
  return http.get('/analysis/graph', { params: { edge_limit: edgeLimit } }) as Promise<GraphVisualizationData>
}
