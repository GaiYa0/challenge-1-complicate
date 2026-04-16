/**
 * 多维可视化：GET /analysis/fund、GET /analysis/trip
 */
import http from './client'

export interface FundTimelineEvent {
  ts: string
  kind: string
  label: string
  amount?: number | null
  from_party?: string | null
  to_party?: string | null
  meta?: Record<string, unknown>
}

export interface FundGraphNode {
  id: string
  name: string
  category?: string
}

export interface FundGraphEdge {
  source: string
  target: string
  value: number
  label: string
}

export interface FundVizData {
  fund_events: FundTimelineEvent[]
  call_events: FundTimelineEvent[]
  anomaly_events: FundTimelineEvent[]
  graph_nodes: FundGraphNode[]
  graph_edges: FundGraphEdge[]
}

export interface TripPoint {
  person_id: string
  lat: number
  lng: number
  ts: string
  weight?: number
}

export interface TripCoOccurrence {
  person_a: string
  person_b: string
  lat: number
  lng: number
  ts: string
  distance_m?: number | null
}

export interface HeatmapCell {
  lng: number
  lat: number
  value: number
}

export interface TripBounds {
  min_lng: number
  max_lng: number
  min_lat: number
  max_lat: number
}

export interface TripVizData {
  points: TripPoint[]
  co_occurrence: TripCoOccurrence[]
  heatmap_cells: HeatmapCell[]
  bounds: TripBounds
}

export function getAnalysisFundViz(edgeLimit = 500): Promise<FundVizData> {
  return http.get('/analysis/fund', { params: { edge_limit: edgeLimit } }) as Promise<FundVizData>
}

export function getAnalysisTripViz(): Promise<TripVizData> {
  return http.get('/analysis/trip') as Promise<TripVizData>
}
