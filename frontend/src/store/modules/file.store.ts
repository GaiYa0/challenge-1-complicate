/**
 * 文件仓库 Store：列表 / 上传 / 预览 / 删除。
 *
 * 所有对 `/api/file`、`/api/upload`、`/api/preview` 的调用必须经过本 store，
 * 视图层只订阅 state 与 actions。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  deleteFileByName,
  getFilePreview,
  listDbFiles,
  uploadFile as uploadFileApi,
  type FileDetailItem,
  type PreviewData,
} from '../../api/file'

export interface FileSummaryItem {
  filename: string
  upload_time?: string
  dataset?: string
  version?: string
}

export interface FilePreviewSnapshot {
  columns: string[]
  preview: Record<string, unknown>[]
}

function normalizeItem(raw: FileDetailItem | { filename: string; upload_time?: string }): FileSummaryItem {
  const r = raw as FileDetailItem
  return {
    filename: String(r?.filename ?? ''),
    upload_time: r?.upload_time ?? undefined,
    dataset: r?.dataset ?? undefined,
    version: r?.version ?? undefined,
  }
}

export const useFileStore = defineStore('file', () => {
  const items = ref<FileSummaryItem[]>([])
  const loading = ref(false)
  const uploading = ref(false)
  const lastError = ref<string | null>(null)
  const activeDataset = ref<string | null>(null)

  /**
   * @param dataset - 按 dataset 过滤（如 `case-123`），null 表示不过滤
   */
  async function fetchList(dataset?: string | null): Promise<FileSummaryItem[]> {
    if (dataset !== undefined) activeDataset.value = dataset ?? null
    loading.value = true
    lastError.value = null
    try {
      const rows = (await listDbFiles()) ?? []
      let normalized = Array.isArray(rows)
        ? rows.map(normalizeItem).filter((i) => i.filename.length > 0)
        : []
      if (activeDataset.value) {
        const ds = activeDataset.value
        normalized = normalized.filter((i) => i.dataset === ds)
      }
      items.value = normalized
      return items.value
    } catch (e) {
      items.value = []
      lastError.value = e instanceof Error ? e.message : String(e)
      return []
    } finally {
      loading.value = false
    }
  }

  async function upload(file: File, params?: { dataset?: string; version?: string }) {
    uploading.value = true
    try {
      const res = await uploadFileApi(file, params)
      await fetchList()
      return res
    } finally {
      uploading.value = false
    }
  }

  async function remove(filename: string) {
    await deleteFileByName(filename)
    await fetchList()
  }

  async function preview(filename: string): Promise<FilePreviewSnapshot> {
    const data = (await getFilePreview(filename)) as PreviewData
    return {
      columns: Array.isArray(data?.columns) ? data.columns : [],
      preview: Array.isArray(data?.preview)
        ? (data.preview as Record<string, unknown>[])
        : [],
    }
  }

  function filenames(): string[] {
    return items.value.map((i) => i.filename).filter((s) => s.length > 0)
  }

  /** 排除 clean_/feature_ 派生文件；用于下游流水线，避免重复清洗/特征抽取。 */
  function sourceFilenames(): string[] {
    return filenames().filter((s) => !s.startsWith('clean_') && !s.startsWith('feature_'))
  }

  function reset() {
    items.value = []
    loading.value = false
    uploading.value = false
    lastError.value = null
  }

  return {
    items,
    loading,
    uploading,
    lastError,
    activeDataset,
    fetchList,
    upload,
    remove,
    preview,
    filenames,
    sourceFilenames,
    reset,
  }
})
