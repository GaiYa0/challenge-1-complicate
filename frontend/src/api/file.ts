import http from './request'

export interface FileUploadData {
  filename: string
  presigned_url: string
  bucket_name: string
  object_name: string
  version: string
  dataset: string
  data_layer: string
}

export interface FileDetailItem {
  filename: string
  bucket_name: string
  object_name: string
  version: string
  dataset: string
  data_layer: string
  upload_time: string | null
  presigned_url: string
  lifecycle_tier: string | null
  archive_format: string | null
  warm_month_key: string | null
}

export interface PreviewData {
  columns: string[]
  dtypes: Record<string, string>
  shape: number[]
  preview: Record<string, unknown>[]
}

export interface CleanData {
  before: number
  after: number
}

export interface CleanRowItem {
  index: number
  status: 'normal' | 'pending' | 'anomaly' | string
  data: Record<string, unknown>
}

export interface CleanRowsData {
  rows: CleanRowItem[]
  total: number
  offset: number
  limit: number
  rows_before: number
  rows_after: number
}

export type ColumnStats = {
  mean?: number | null
  max?: number | null
  min?: number | null
}

export type StatsMap = Record<string, ColumnStats>

export interface AnomalyData {
  anomaly_count: number
}

function enc(name: string) {
  return encodeURIComponent(name)
}

export function listDbFiles(): Promise<FileDetailItem[]> {
  return http.get('/db/files') as Promise<FileDetailItem[]>
}

export function uploadFile(
  file: File,
  params?: { dataset?: string; version?: string },
): Promise<FileUploadData> {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/upload', fd, {
    params: {
      dataset: params?.dataset ?? 'default',
      version: params?.version ?? 'v1',
    },
    timeout: 120_000,
  }) as Promise<FileUploadData>
}

export function deleteFileByName(filename: string): Promise<void> {
  return http.delete(`/file/${enc(filename)}`) as Promise<void>
}

export function getFilePreview(filename: string): Promise<PreviewData> {
  return http.get(`/preview/${enc(filename)}`) as Promise<PreviewData>
}

export function getFileClean(filename: string): Promise<CleanData> {
  return http.get(`/clean/${enc(filename)}`) as Promise<CleanData>
}

export function getFileCleanRows(
  filename: string,
  params?: { offset?: number; limit?: number },
): Promise<CleanRowsData> {
  return http.get(`/clean/rows/${enc(filename)}`, {
    params: {
      offset: params?.offset ?? 0,
      limit: params?.limit ?? 200,
    },
  }) as Promise<CleanRowsData>
}

export function getFileStats(filename: string): Promise<StatsMap> {
  return http.get(`/stats/${enc(filename)}`) as Promise<StatsMap>
}

export function getFileAnomaly(filename: string): Promise<AnomalyData> {
  return http.get(`/anomaly/${enc(filename)}`) as Promise<AnomalyData>
}
