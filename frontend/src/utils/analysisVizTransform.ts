/**
 * 多维可视化：后端数据 → ECharts option（纯函数，便于单测与复用）
 */
import type { EChartsOption } from 'echarts'
import type {
  FundGraphEdge,
  FundGraphNode,
  FundTimelineEvent,
  FundVizData,
  HeatmapCell,
  TripCoOccurrence,
  TripPoint,
  TripVizData,
} from '../api/analysisViz'

export type TimeLineFilters = {
  fund: boolean
  call: boolean
  anomaly: boolean
}

const Y_LABELS = ['资金', '通话', '异常'] as const

function eventToPoint(ev: FundTimelineEvent, yIndex: 0 | 1 | 2): [string, string, string, number?] {
  const extra = [ev.from_party, ev.to_party].filter(Boolean).join('→')
  const name = [ev.label, extra].filter(Boolean).join(' ')
  return [ev.ts, Y_LABELS[yIndex], name, ev.amount ?? undefined]
}

/** 时间轴：分类 Y + 时间 X，dataZoom 缩放；三类事件分系列便于图例筛选 */
export function buildTimeLineOption(
  data: Pick<FundVizData, 'fund_events' | 'call_events' | 'anomaly_events'>,
  filters: TimeLineFilters,
): EChartsOption {
  const fundData: [string, string, string, number?][] = []
  const callData: [string, string, string, number?][] = []
  const anoData: [string, string, string, number?][] = []

  if (filters.fund) {
    data.fund_events.forEach((e) => fundData.push(eventToPoint(e, 0)))
  }
  if (filters.call) {
    data.call_events.forEach((e) => callData.push(eventToPoint(e, 1)))
  }
  if (filters.anomaly) {
    data.anomaly_events.forEach((e) => anoData.push(eventToPoint(e, 2)))
  }

  return {
    title: { text: '多源事件时间轴', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const x = p as { value?: unknown[]; seriesName?: string }
        const v = x.value
        if (Array.isArray(v) && v.length >= 3) {
          const amt = v[3] != null ? `<br/>金额: ${v[3]}` : ''
          return `${v[0]}<br/>${x.seriesName ?? ''}<br/>${v[2]}${amt}`
        }
        return String(p)
      },
    },
    legend: { bottom: 0, data: ['交易', '通话', '异常事件'] },
    grid: { left: 72, right: 48, top: 48, bottom: 72 },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'weakFilter' },
      { type: 'slider', xAxisIndex: 0, height: 22, bottom: 36 },
    ],
    xAxis: {
      type: 'time',
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'category',
      data: [...Y_LABELS],
      axisLine: { show: true },
      splitLine: { show: true },
    },
    series: [
      {
        name: '交易',
        type: 'scatter',
        symbolSize: (val: unknown) => {
          const a = (val as number[])?.[3]
          if (typeof a === 'number' && a > 0) {
            return Math.min(22, 8 + Math.log10(a + 1) * 3)
          }
          return 10
        },
        itemStyle: { color: '#5470c6' },
        data: fundData,
        encode: { x: 0, y: 1 },
      },
      {
        name: '通话',
        type: 'scatter',
        symbol: 'triangle',
        symbolSize: 12,
        itemStyle: { color: '#91cc75' },
        data: callData,
        encode: { x: 0, y: 1 },
      },
      {
        name: '异常事件',
        type: 'scatter',
        symbol: 'diamond',
        symbolSize: 14,
        itemStyle: { color: '#ee6666' },
        data: anoData,
        encode: { x: 0, y: 1 },
      },
    ],
  }
}

function edgeWidth(value: number, minV: number, maxV: number): number {
  if (maxV <= minV) return 3
  const t = (value - minV) / (maxV - minV)
  return 2 + t * 10
}

/** 有向资金流向图：力导向 + 箭头 + 边宽表示金额；高亮路径用 edge emphasis */
export function buildFundFlowGraphOption(
  nodes: FundGraphNode[],
  edges: FundGraphEdge[],
  highlightEdgeIds?: Set<string>,
): EChartsOption {
  const amounts = edges.map((e) => e.value)
  const minV = amounts.length ? Math.min(...amounts) : 0
  const maxV = amounts.length ? Math.max(...amounts) : 1

  const nData = nodes.map((n) => ({
    id: n.id,
    name: n.name,
    category: 0,
    symbolSize: 28,
    label: { show: true },
  }))

  const eData = edges.map((e, i) => {
    const id = `${e.source}>${e.target}>${i}`
    const hl = highlightEdgeIds?.has(id)
    return {
      id,
      source: e.source,
      target: e.target,
      value: e.value,
      label: { show: true, formatter: e.label || String(e.value) },
      lineStyle: {
        width: edgeWidth(e.value, minV, maxV),
        curveness: 0.12,
        color: hl ? '#fac858' : '#aaa',
        opacity: hl ? 1 : 0.85,
      },
    }
  })

  return {
    title: { text: '资金流向（有向，边宽∝金额）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      formatter: (x: unknown) => {
        const p = x as { dataType?: string; data?: { value?: number; source?: string; target?: string } }
        if (p.dataType === 'edge' && p.data) {
          return `${p.data.source} → ${p.data.target}<br/>金额: ${p.data.value}`
        }
        return ''
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        force: {
          repulsion: 420,
          edgeLength: [80, 160],
          gravity: 0.12,
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 12],
        label: { position: 'right' },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 6, color: '#fac858' },
        },
        categories: [{ name: '账户' }],
        data: nData,
        links: eData,
        lineStyle: { opacity: 0.9 },
      },
    ],
  }
}

/** 根据起点终点高亮一条链上的边（按 links 顺序匹配） */
export function highlightPathEdgeIds(
  edges: FundGraphEdge[],
  path: string[],
): Set<string> {
  const set = new Set<string>()
  if (path.length < 2) return set
  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i]
    const b = path[i + 1]
    const idx = edges.findIndex((e) => e.source === a && e.target === b)
    if (idx >= 0) {
      set.add(`${a}>${b}>${idx}`)
    }
  }
  return set
}

/** 轨迹热力：经纬度平面 + 热力格 + 伴随点；无地图底图，便于离线部署 */
export function buildTripHeatmapOption(data: TripVizData): EChartsOption {
  const b = data.bounds
  const padX = (b.max_lng - b.min_lng) * 0.05 || 0.01
  const padY = (b.max_lat - b.min_lat) * 0.05 || 0.01

  const heat = data.heatmap_cells.map((c: HeatmapCell) => [c.lng, c.lat, c.value] as [number, number, number])
  const maxH = heat.length ? Math.max(...heat.map((x) => x[2])) : 1

  const scatP = data.points.map((p: TripPoint) => ({
    value: [p.lng, p.lat, p.person_id, p.ts],
    symbolSize: 6 + (p.weight ?? 1) * 2,
  }))
  const scatC = data.co_occurrence.map((c: TripCoOccurrence) => ({
    value: [c.lng, c.lat, `${c.person_a}/${c.person_b}`, c.ts],
    symbolSize: 14,
    itemStyle: { color: '#ee6666' },
  }))

  return {
    title: { text: '出行轨迹 / 时空伴随 / 热力聚合', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const v = (p as { value?: unknown[]; seriesName?: string }).value
        if (Array.isArray(v) && v.length >= 4) {
          return `${v[2]}<br/>${v[3]}<br/>lng:${v[0]} lat:${v[1]}`
        }
        if (Array.isArray(v) && v.length >= 3) {
          return `热力强度: ${v[2]}<br/>lng:${v[0]} lat:${v[1]}`
        }
        return String(p)
      },
    },
    grid: { left: 56, right: 88, top: 44, bottom: 56 },
    xAxis: {
      type: 'value',
      name: '经度',
      min: b.min_lng - padX,
      max: b.max_lng + padX,
      scale: true,
    },
    yAxis: {
      type: 'value',
      name: '纬度',
      min: b.min_lat - padY,
      max: b.max_lat + padY,
      scale: true,
    },
    visualMap: [
      {
        show: true,
        right: 12,
        top: 'middle',
        min: 0,
        max: maxH || 1,
        dimension: 2,
        seriesIndex: 0,
        inRange: { color: ['#313695', '#4575b4', '#74add1', '#fdae61', '#d73027'] },
        text: ['高', '低'],
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0], yAxisIndex: [0] },
      { type: 'slider', xAxisIndex: 0, bottom: 8, height: 18 },
    ],
    series: [
      {
        name: '热力(聚合)',
        type: 'heatmap',
        data: heat,
        progressive: 400,
        emphasis: { itemStyle: { shadowBlur: 12 } },
      },
      {
        name: '轨迹点',
        type: 'scatter',
        data: scatP,
        itemStyle: { color: '#5470c6', opacity: 0.75 },
        large: true,
        largeThreshold: 500,
      },
      {
        name: '时空伴随',
        type: 'scatter',
        data: scatC,
        symbol: 'pin',
      },
    ],
  }
}
