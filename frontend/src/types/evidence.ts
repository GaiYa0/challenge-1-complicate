/**
 * 证据链核心类型定义
 * 系统核心结构：嫌疑人 → 行为 → 证据 → 关联人 → 结论
 */

/** 行为类型 */
export type ActionType = 'fund' | 'call' | 'trip' | 'other'

/** 证据状态 */
export type EvidenceStatus = 'confirmed' | 'pending' | 'rejected'

/** 行为节点 */
export interface EvidenceAction {
  id: string
  type: ActionType
  label: string
  time: string
  description: string
  amount?: number
}

/** 单条证据 */
export interface Evidence {
  id: string
  actionId: string
  source: string
  sourceType: string
  recordId: string
  ruleHit: string
  rawContent: string
  remark: string
  status: EvidenceStatus
  time: string
}

/** 关联人 */
export interface RelatedPerson {
  id: string
  name: string
  role: string
  relation: string
  evidenceIds: string[]
}

/** 嫌疑人 */
export interface Suspect {
  id: string
  name: string
  caseNumber: string
  tags: string[]
  summary: string
}

/** 按对手合并时附带的逐笔（来自 portrait fund_counterparty_lines.rows） */
export interface FundTxRowLite {
  amount: number
  time?: string | null
}

/** 证据链条目（时间轴用） */
export interface EvidenceChainEntry {
  time: string
  action: EvidenceAction
  evidences: Evidence[]
  relatedPersons: RelatedPerson[]
  /** 仅资金合并行：展开区展示逐笔用 */
  fundTxRows?: FundTxRowLite[]
  /** 对方合并行的交易笔数（与 fundTxRows 长度对比以决定是否提示截断） */
  fundLineTxCount?: number
}

/** 证据链 */
export interface EvidenceChain {
  suspect: Suspect
  entries: EvidenceChainEntry[]
}

/** 证据图节点类型 */
export type EvidenceNodeKind = 'suspect' | 'action' | 'evidence' | 'person'

/** 证据图节点 */
export interface EvidenceGraphNode {
  id: string
  kind: EvidenceNodeKind
  label: string
  data?: Record<string, unknown>
}

/** 证据图边 */
export interface EvidenceGraphEdge {
  id: string
  source: string
  target: string
  label: string
  actionType?: ActionType
  /** 资金边权（元或笔数），用于线宽 */
  weight?: number
}

/** 证据图数据 */
export interface EvidenceGraphData {
  nodes: EvidenceGraphNode[]
  edges: EvidenceGraphEdge[]
}

/** 清洗行标记状态 */
export type CleanRowStatus = 'normal' | 'anomaly' | 'pending'

/** 清洗行条目 */
export interface CleanRowEntry {
  index: number
  status: CleanRowStatus
  markedAsEvidence: boolean
  remark: string
  data: Record<string, unknown>
}

/** 行为类型中文映射 */
export const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  fund: '资金往来',
  call: '通话记录',
  trip: '出行轨迹',
  other: '其他行为',
}

/** 节点颜色映射 */
export const NODE_KIND_COLORS: Record<EvidenceNodeKind, { fill: string; stroke: string; text: string }> = {
  suspect: { fill: '#fecaca', stroke: '#dc2626', text: '#991b1b' },
  action: { fill: '#bfdbfe', stroke: '#2563eb', text: '#1e40af' },
  evidence: { fill: '#fef08a', stroke: '#ca8a04', text: '#854d0e' },
  person: { fill: '#e5e7eb', stroke: '#6b7280', text: '#374151' },
}
