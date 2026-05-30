/**
 * 报告导出：POST /reports/generate，轮询 GET /reports/tasks/{task_id}
 */
import http from './client'

export interface ReportGenerateBody {
  case_id: number
  person_id: string
  format?: 'pdf' | 'docx'
  /** 合规开启时普通用户必填：已审批的导出申请 ID */
  export_request_id?: number
}

export interface ReportTaskQueued {
  task_id: string
  status: string
  poll_url: string
}

export interface ReportTaskResult {
  task_id: string
  status: string
  result: {
    download_url: string
    bucket: string
    object_name: string
    expires_in_seconds: number
    format: string
  } | null
  error: string | null
}

export function generateReport(body: ReportGenerateBody) {
  return http.post('/reports/generate', {
    case_id: body.case_id,
    person_id: body.person_id,
    format: body.format ?? 'pdf',
    export_request_id: body.export_request_id,
  }) as Promise<ReportTaskQueued>
}

export function getReportTask(taskId: string) {
  return http.get(`/reports/tasks/${encodeURIComponent(taskId)}`, {
    skipGlobalLoading: true,
  } as Parameters<typeof http.get>[1]) as Promise<ReportTaskResult>
}
