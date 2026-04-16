/**
 * 领域核心类型（与后端契约对齐，不含展示层字段）。
 * 具体接口返回可在此基础上扩展 Pick / 组合。
 */

/** 案件 */
export interface Case {
  id: number
  user_id?: number
  name: string
  case_number: string | null
  note: string | null
  status: string
  extra_metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type ClueRiskLevel = 'high' | 'medium' | 'low'

export type ClueCategory = 'fund' | 'call' | 'trip' | 'other'

/** 线索（与 Neo4j User.name 对齐的 person_id） */
export interface Clue {
  id: number
  case_id: number
  person_id: string
  title: string
  summary: string | null
  risk_level: ClueRiskLevel | string
  risk_score: number
  category: ClueCategory | string
  rule_hits: unknown[]
  feature_snapshot: Record<string, unknown>
  risk_prompts: unknown[]
  created_at: string
  updated_at: string
}

/** 图谱节点（可视化与 Neo4j 投影共用最小集） */
export interface GraphNode {
  id: string
  label: string
  /** 业务类型：person / account / org / clue / … */
  kind?: string
  data?: Record<string, unknown>
}

/** 图谱边 */
export interface GraphEdge {
  id: string
  source: string
  target: string
  /** 关系类型或业务标签 */
  label?: string
  data?: Record<string, unknown>
}

export type AnalysisTaskStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

/** 领域分析任务（对应后端 analysis_tasks） */
export interface AnalysisTask {
  id: number
  public_id: string
  case_id: number
  user_id: number | null
  task_type: string
  status: AnalysisTaskStatus | string
  input_payload: Record<string, unknown>
  result_ref: Record<string, unknown> | null
  error_message: string | null
  celery_task_id: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}
