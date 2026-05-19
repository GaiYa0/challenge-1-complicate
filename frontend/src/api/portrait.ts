import http from './client'
import type { GraphVisualizationData } from './graph'

export interface PortraitBasicInfo {
  case_id: number
  person_id: string
  display_name: string
  risk_score: number
  risk_level: string
  summary: string
}

export interface PortraitFundTxRow {
  amount: number
  /** 表格解析出的交易/单据时间 */
  time?: string | null
}

export interface PortraitFundLine {
  counterparty: string
  amount: number
  tx_count: number
  /** 该对手下已解析的最早/最晚时间（合并行展示与排序用） */
  earliest_time?: string | null
  latest_time?: string | null
  /** 可选逐笔明细（后端有上限） */
  rows?: PortraitFundTxRow[]
}

export interface PortraitEconomic {
  total_amount: number
  anomaly_ratio: number
  transfer_out_count: number
  transfer_in_count: number
  explain: string
  /** 本案仅财付通表格 */
  fund_only_evidence?: boolean
  /** 按对手侧合并后的真实金额行 */
  fund_counterparty_lines?: PortraitFundLine[]
}

export interface TimelineBin {
  hour: number
  count: number
}

export interface MapPoint {
  lat: number
  lng: number
  ts: string
  label: string
}

export interface PortraitBehavior {
  timeline_bins: TimelineBin[]
  map_points: MapPoint[]
  bounds: Record<string, number>
  explain: string
}

export interface PortraitSocial {
  graph: GraphVisualizationData
  center_id: string
  explain: string
}

export interface PortraitClueItem {
  id: number
  title: string
  risk_level: string
  risk_score: number
  category: string
  /** 线索入库时间 */
  created_at?: string | null
}

export interface PersonPortrait {
  basic_info: PortraitBasicInfo
  economic: PortraitEconomic
  behavior: PortraitBehavior
  social: PortraitSocial
  clues: PortraitClueItem[]
  links: Record<string, string>
}

/** GET /cases/{case_id}/persons/{person_id}/portrait */
export function getPersonPortrait(caseId: number, personId: string) {
  const pid = encodeURIComponent(personId)
  return http.get(`/cases/${caseId}/persons/${pid}/portrait`) as Promise<PersonPortrait>
}
