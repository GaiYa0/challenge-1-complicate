import type { GraphVisualizationData } from '../api/graph'

/** 与后端 GRAPH_NODE_CAP 对齐，避免 G6 一次挂载过多元素 */
export const GRAPH_DISPLAY_MAX_NODES = 100

export function clipGraphVisualization(
  data: GraphVisualizationData,
  maxNodes: number = GRAPH_DISPLAY_MAX_NODES,
): GraphVisualizationData {
  if (data.nodes.length <= maxNodes) return data
  const kept = new Set(data.nodes.slice(0, maxNodes).map((n) => n.id))
  const edges = data.edges.filter((e) => kept.has(e.source) && kept.has(e.target))
  return { nodes: data.nodes.slice(0, maxNodes), edges }
}
