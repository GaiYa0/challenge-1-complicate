/**
 * 人物画像页：ECharts 配置（由后端 portrait.behavior / social 转换）
 */
import type { EChartsOption } from 'echarts'
import type { PortraitBehavior, TimelineBin } from '../api/portrait'
import type { FundGraphEdge, FundGraphNode, HeatmapCell, TripVizData } from '../api/analysisViz'
import type { GraphVisualizationData } from '../api/graph'
import { buildFundFlowGraphOption, buildTripHeatmapOption } from './analysisVizTransform'

export function buildBehaviorTimelineOption(bins: TimelineBin[]): EChartsOption {
  const labels = bins.map((b) => `${b.hour}:00`)
  return {
    title: { text: '定位时间分布（按小时）', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 40, bottom: 48 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '次数' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
    series: [
      {
        type: 'bar',
        name: '轨迹点数',
        data: bins.map((b) => b.count),
        itemStyle: { color: '#5470c6' },
      },
    ],
  }
}

function aggregateCells(
  points: { lng: number; lat: number }[],
  cellDeg = 0.004,
): HeatmapCell[] {
  const buckets = new Map<string, number>()
  for (const p of points) {
    const gx = Math.round(p.lng / cellDeg)
    const gy = Math.round(p.lat / cellDeg)
    const k = `${gx},${gy}`
    buckets.set(k, (buckets.get(k) ?? 0) + 1)
  }
  return Array.from(buckets.entries()).map(([k, v]) => {
    const [gx, gy] = k.split(',').map(Number)
    return {
      lng: (gx + 0.5) * cellDeg,
      lat: (gy + 0.5) * cellDeg,
      value: v,
    }
  })
}

export function behaviorToTripViz(b: PortraitBehavior): TripVizData {
  const pts = b.map_points.map((m) => ({
    person_id: 'portrait',
    lat: m.lat,
    lng: m.lng,
    ts: m.ts,
    weight: 1,
  }))
  const heat = aggregateCells(b.map_points)
  const bounds = b.bounds
  return {
    points: pts,
    co_occurrence: [],
    heatmap_cells: heat,
    bounds: {
      min_lng: bounds.min_lng ?? 116.3,
      max_lng: bounds.max_lng ?? 116.5,
      min_lat: bounds.min_lat ?? 39.8,
      max_lat: bounds.max_lat ?? 40.0,
    },
  }
}

export function buildPortraitMapOption(behavior: PortraitBehavior): EChartsOption {
  return buildTripHeatmapOption(behaviorToTripViz(behavior))
}

export function graphToFundFlowOption(g: GraphVisualizationData): EChartsOption {
  const nodes: FundGraphNode[] = g.nodes.map((n) => ({
    id: n.id,
    name: n.label,
    category: 'account',
  }))
  const edges: FundGraphEdge[] = g.edges.map((e, i) => ({
    source: e.source,
    target: e.target,
    value: 20_000 + (i % 8) * 10_000,
    label: '',
  }))
  return buildFundFlowGraphOption(nodes, edges)
}
