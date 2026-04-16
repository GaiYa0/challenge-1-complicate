/**
 * 线索详情侧栏类型（与后端 ClueDetailOut / GET /clues/{id} 对齐）
 */
import type { ClueDetail } from '../api/clue'

export type { ClueDetail }

/** 侧栏数据视图状态 */
export type ClueDetailPanelView = 'loading' | 'empty' | 'error' | 'ready'

/** rule_hits / risk_prompts 单项可为字符串或结构化对象 */
export type ClueJsonItem = string | number | boolean | null | Record<string, unknown> | unknown[]

/** 将 rule_hits 项渲染为短标签文案 */
export function formatRuleHitLabel(item: unknown): string {
  if (item == null) return '—'
  if (typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean') {
    return String(item)
  }
  if (typeof item === 'object') {
    const o = item as Record<string, unknown>
    if (typeof o.name === 'string') return o.name
    if (typeof o.rule === 'string') return o.rule
    if (typeof o.label === 'string') return o.label
    try {
      return JSON.stringify(item)
    } catch {
      return '[object]'
    }
  }
  return String(item)
}

/** 将 risk_prompts 项渲染为可读段落 */
export function formatRiskPromptText(item: unknown): string {
  if (item == null) return ''
  if (typeof item === 'string') return item
  if (typeof item === 'object') {
    const o = item as Record<string, unknown>
    if (typeof o.text === 'string') return o.text
    if (typeof o.message === 'string') return o.message
    try {
      return JSON.stringify(item, null, 2)
    } catch {
      return String(item)
    }
  }
  return String(item)
}

/** feature_snapshot 扁平为表格行 */
export function featureSnapshotToRows(snapshot: Record<string, unknown>): { key: string; value: string }[] {
  return Object.entries(snapshot).map(([key, val]) => ({
    key,
    value: formatFeatureValue(val),
  }))
}

function formatFeatureValue(val: unknown): string {
  if (val == null) return '—'
  if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') {
    return String(val)
  }
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

/** 风险等级 → Element Plus tag type */
export function riskLevelTagType(level: string): 'danger' | 'warning' | 'info' | 'success' {
  const s = String(level || '').toLowerCase()
  if (s === 'high') return 'danger'
  if (s === 'medium') return 'warning'
  if (s === 'low') return 'info'
  return 'success'
}
