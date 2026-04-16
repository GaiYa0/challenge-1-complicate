/**
 * 合规：导出审批、审计日志、策略说明
 */
import http from './client'

export interface ExportRequestOut {
  id: number
  applicant_id: number
  case_id: number
  person_id: string
  file_format: string
  status: string
  reviewer_id: number | null
  review_note: string | null
  reviewed_at: string | null
  created_at: string
}

export interface AuditLogOut {
  id: number
  user_id: number | null
  case_id: number | null
  action: string
  resource_type: string
  resource_id: string | null
  ip_address: string | null
  detail: Record<string, unknown> | null
  created_at: string
}

export function createExportRequest(body: {
  case_id: number
  person_id: string
  file_format: 'pdf' | 'docx'
}) {
  return http.post<ExportRequestOut>('/compliance/export-requests', body)
}

export function listExportRequests(scope: 'mine' | 'all' = 'mine') {
  return http.get<ExportRequestOut[]>('/compliance/export-requests', {
    params: { scope },
  })
}

export function approveExportRequest(id: number, note?: string) {
  return http.post<ExportRequestOut>(`/compliance/export-requests/${id}/approve`, { note })
}

export function rejectExportRequest(id: number, note?: string) {
  return http.post<ExportRequestOut>(`/compliance/export-requests/${id}/reject`, { note })
}

export function listAuditLogs(params?: {
  user_id?: number
  case_id?: number
  action_prefix?: string
  limit?: number
}) {
  return http.get<AuditLogOut[]>('/compliance/audit-logs', { params })
}

export function getComplianceSettings() {
  return http.get<{ export_approval_required: boolean; masking: Record<string, string> }>(
    '/compliance/settings',
  )
}
