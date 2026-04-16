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

export interface PortraitEconomic {
  total_amount: number
  anomaly_ratio: number
  transfer_out_count: number
  transfer_in_count: number
  explain: string
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
