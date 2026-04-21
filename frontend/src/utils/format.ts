/**
 * 全站统一的时间 / 金额 / 文件大小 / 状态等显示格式化工具。
 *
 * 视图层禁止手写 toLocaleString / toFixed 散落式格式化逻辑，统一走这里。
 */
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import relativeTime from 'dayjs/plugin/relativeTime'
import utc from 'dayjs/plugin/utc'

dayjs.extend(relativeTime)
dayjs.extend(utc)
dayjs.locale('zh-cn')

export type DateInput = string | number | Date | null | undefined

export function formatDateTime(input: DateInput, pattern = 'YYYY-MM-DD HH:mm'): string {
  if (input === null || input === undefined || input === '') return '—'
  const d = dayjs(input)
  if (!d.isValid()) return String(input)
  return d.format(pattern)
}

export function formatDate(input: DateInput, pattern = 'YYYY-MM-DD'): string {
  return formatDateTime(input, pattern)
}

/** 相对时间：3 分钟前 / 2 小时前 / 昨天 */
export function formatRelative(input: DateInput, fallback = '—'): string {
  if (input === null || input === undefined || input === '') return fallback
  const d = dayjs(input)
  if (!d.isValid()) return fallback
  const diff = Math.abs(dayjs().diff(d, 'day'))
  if (diff > 30) return d.format('YYYY-MM-DD')
  return d.fromNow()
}

/** 人民币金额：166500 → ¥166,500.00 */
export function formatAmount(value: number | string | null | undefined, opts?: {
  currency?: string
  fractionDigits?: number
  compact?: boolean
}): string {
  const currency = opts?.currency ?? '¥'
  const digits = opts?.fractionDigits ?? 2
  const n = Number(value)
  if (!Number.isFinite(n)) return `${currency}—`
  if (opts?.compact && Math.abs(n) >= 10000) {
    if (Math.abs(n) >= 1e8) return `${currency}${(n / 1e8).toFixed(2)} 亿`
    if (Math.abs(n) >= 1e4) return `${currency}${(n / 1e4).toFixed(2)} 万`
  }
  return `${currency}${n.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`
}

/** 纯数字千分位 */
export function formatNumber(value: number | string | null | undefined, digits = 0): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** 0.4321 → 43.21% */
export function formatPercent(value: number | string | null | undefined, digits = 2): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

/** 1024 → 1 KB；1048576 → 1.00 MB */
export function formatFileSize(bytes: number | string | null | undefined): string {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n < 0) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 100 ? 0 : v >= 10 ? 1 : 2)} ${units[i]}`
}

/** 从文件名推断扩展（用于分组） */
export function getFileExtension(filename: string): string {
  const idx = filename.lastIndexOf('.')
  if (idx < 0 || idx === filename.length - 1) return ''
  return filename.slice(idx + 1).toLowerCase()
}

export type StatusTone = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'

export interface StatusDescriptor {
  label: string
  tone: StatusTone
}

/** 把业务状态字符串统一翻译成 {label, tone}，给 `<StatusTag>` 使用。 */
export function resolveStatus(raw: string | null | undefined): StatusDescriptor {
  const v = String(raw ?? '').toLowerCase()
  switch (v) {
    case 'completed':
    case 'success':
    case 'done':
      return { label: '已完成', tone: 'success' }
    case 'processing':
    case 'running':
    case 'in_progress':
      return { label: '进行中', tone: 'primary' }
    case 'pending':
    case 'queued':
      return { label: '排队中', tone: 'info' }
    case 'failed':
    case 'error':
      return { label: '失败', tone: 'danger' }
    case 'canceled':
    case 'cancelled':
      return { label: '已取消', tone: 'default' }
    case 'high':
      return { label: '高风险', tone: 'danger' }
    case 'medium':
      return { label: '中风险', tone: 'warning' }
    case 'low':
      return { label: '低风险', tone: 'success' }
    default:
      return { label: raw ? String(raw) : '—', tone: 'default' }
  }
}
