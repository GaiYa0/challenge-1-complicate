/**
 * 风险评估 Store：特征提取任务编排 + 同步预测 + 风险等级映射。
 *
 * 视图层仅调用本 store 暴露的 actions，业务映射（prediction → risk score → level）
 * 统一集中到此处，杜绝视图侧计算分数逻辑。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

import { extractFeatureJob } from '../../api/feature'
import { predictSync } from '../../api/model'

const DERIVATIVE_PREFIXES: ReadonlyArray<string> = ['clean_', 'feature_']

function isDerivativeFilename(name: string): boolean {
  return DERIVATIVE_PREFIXES.some((p) => name.startsWith(p))
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)))
}

export type RiskLevel = 'low' | 'medium' | 'high'

export interface RiskSnapshot {
  riskScore: number
  riskLevel: RiskLevel
  prediction: number | null
  /** 当后端返回“暂无可用模型”等可恢复错误时，向视图层暴露提示文案 */
  note?: string | null
}

const DEFAULT_SNAPSHOT: RiskSnapshot = {
  riskScore: 0,
  riskLevel: 'low',
  prediction: null,
  note: null,
}

function deriveLevel(score: number): RiskLevel {
  if (score > 70) return 'high'
  if (score > 30) return 'medium'
  return 'low'
}

function mapPredictionToScore(prediction: number | null | undefined): number {
  const p = Number(prediction)
  if (!Number.isFinite(p)) return 50
  return p === 1 ? 78 : 22
}

export const useRiskStore = defineStore('risk', () => {
  const enqueueing = ref(false)
  const enqueuedTaskIds = ref<string[]>([])
  const predicting = ref(false)
  const snapshot = ref<RiskSnapshot>({ ...DEFAULT_SNAPSHOT })

  async function enqueueFeatureJobs(filenames: readonly string[]): Promise<string[]> {
    const names = filenames.filter(
      (n): n is string =>
        typeof n === 'string' && n.length > 0 && !isDerivativeFilename(n),
    )
    if (names.length === 0) {
      enqueuedTaskIds.value = []
      return []
    }
    enqueueing.value = true
    const ids: string[] = []
    try {
      for (const filename of names) {
        try {
          const res = await extractFeatureJob(filename)
          const tid = typeof res?.task_id === 'string' ? res.task_id : ''
          if (tid) ids.push(tid)
        } catch (e) {
          console.warn('[risk.store] enqueue failed', filename, e)
        }
        await sleep(150)
      }
      enqueuedTaskIds.value = ids
      return ids
    } finally {
      enqueueing.value = false
    }
  }

  async function evaluate(filename: string | undefined): Promise<RiskSnapshot> {
    if (!filename) {
      snapshot.value = { ...DEFAULT_SNAPSHOT }
      return snapshot.value
    }
    predicting.value = true
    try {
      try {
        const res = await predictSync(filename)
        const prediction = Number.isFinite(res?.prediction) ? Number(res.prediction) : null
        const score = mapPredictionToScore(prediction)
        snapshot.value = {
          riskScore: score,
          riskLevel: deriveLevel(score),
          prediction,
          note: null,
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e ?? '')
        const noModel = /no deployable model|model version not found|no feature rows/i.test(msg)
        console.warn('[risk.store] predict failed, fallback to medium', e)
        snapshot.value = {
          riskScore: 50,
          riskLevel: 'medium',
          prediction: null,
          note: noModel
            ? '暂无已部署的风险模型，已回退为中等风险的经验值（完成特征抽取后会自动重试并训练）'
            : '风险预测暂时不可用，已回退为中等风险的经验值',
        }
      }
      return snapshot.value
    } finally {
      predicting.value = false
    }
  }

  function applyCached(input: unknown): RiskSnapshot {
    const obj = (input ?? {}) as Partial<RiskSnapshot>
    const rawScore = Number(obj.riskScore)
    const score = Number.isFinite(rawScore) ? rawScore : 0
    const allowed: RiskLevel[] = ['low', 'medium', 'high']
    const level: RiskLevel = allowed.includes(obj.riskLevel as RiskLevel)
      ? (obj.riskLevel as RiskLevel)
      : deriveLevel(score)
    const prediction =
      typeof obj.prediction === 'number' && Number.isFinite(obj.prediction) ? obj.prediction : null
    const note = typeof obj.note === 'string' && obj.note.length > 0 ? obj.note : null
    const next: RiskSnapshot = { riskScore: score, riskLevel: level, prediction, note }
    snapshot.value = next
    return next
  }

  function reset() {
    enqueueing.value = false
    enqueuedTaskIds.value = []
    predicting.value = false
    snapshot.value = { ...DEFAULT_SNAPSHOT }
  }

  return {
    enqueueing,
    enqueuedTaskIds,
    predicting,
    snapshot,
    enqueueFeatureJobs,
    evaluate,
    applyCached,
    reset,
  }
})
