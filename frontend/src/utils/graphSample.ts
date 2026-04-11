import type { EdgeData, NodeData } from '@antv/g6'

/** 生成一条链路上的大量节点（用于压测 G6） */
export function buildLineGraphData(nodeCount: number): { nodes: NodeData[]; edges: EdgeData[] } {
  const nodes: NodeData[] = Array.from({ length: nodeCount }, (_, i) => ({
    id: `N${i}`,
    data: { label: String(i) },
  }))
  const edges: EdgeData[] = Array.from({ length: nodeCount - 1 }, (_, i) => ({
    id: `E${i}`,
    source: `N${i}`,
    target: `N${i + 1}`,
  }))
  return { nodes, edges }
}

/** 只保留前 maxNodes 个节点及两端都在其中的边，避免首屏一次挂载过多元素 */
export function clipGraphData(
  nodes: NodeData[],
  edges: EdgeData[],
  maxNodes: number,
): { nodes: NodeData[]; edges: EdgeData[] } {
  if (nodes.length <= maxNodes) return { nodes, edges }
  const kept = new Set(nodes.slice(0, maxNodes).map((n) => String(n.id)))
  const n2 = nodes.slice(0, maxNodes)
  const e2 = edges.filter((e) => kept.has(String(e.source)) && kept.has(String(e.target)))
  return { nodes: n2, edges: e2 }
}
