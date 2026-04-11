import http from './request'

export interface PieSlice {
  name: string
  value: number
}

export interface AnalysisTableRow {
  id: number
  name: string
  metric: number
  status: string
}

/** 与后端 AnalysisDashboardData 对齐 */
export interface AnalysisDashboardData {
  headline: string
  trend_labels: string[]
  trend_values: number[]
  bar_labels: string[]
  bar_values: number[]
  pie: PieSlice[]
  table: AnalysisTableRow[]
}

export function getAnalysisDashboard(): Promise<AnalysisDashboardData> {
  return http.get('/analysis/dashboard') as Promise<AnalysisDashboardData>
}
