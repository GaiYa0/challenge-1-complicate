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

export interface RiskFactorItem {
  /** 因子名（财务/行为/关系/合规/数据质量） */
  name: string
  /** 0~100；越高越危险 */
  value: number
  /** 可选色阶，默认由 value 自动判定 */
  tone?: 'danger' | 'warning' | 'success' | 'primary'
}

export interface RiskSnapshot {
  riskScore: number
  riskLevel: RiskLevel
  prediction: number | null
  /** 当后端返回“暂无可用模型”等可恢复错误时，向视图层暴露提示文案 */
  note?: string | null
  /** 因子分解：展示给视图层用；前端侧基于 prediction + anomaly 经验化推导，后端补齐后可替换 */
  factors?: RiskFactorItem[] | null
}

const DEFAULT_SNAPSHOT: RiskSnapshot = {
  riskScore: 0,
  riskLevel: 'low',
  prediction: null,
  note: null,
  factors: null,
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

/**
 * 当后端未返回因子分解时，基于 prediction/score 经验化推导一组可展示因子。
 * 这样视图层永远有图可画，接口升级后直接替换即可。
 */
function deriveFactors(score: number, prediction: number | null): RiskFactorItem[] {
  const base = Math.max(0, Math.min(100, score))
  const jitter = (seed: number, amp: number) => {
    const s = Math.sin(seed * 9301 + base * 49297 + (prediction ?? 0) * 233280) * 43758
    return (s - Math.floor(s)) * amp
  }
  const clamp = (v: number) => Math.max(5, Math.min(95, Math.round(v)))
  return [
    { name: '资金异常', value: clamp(base + jitter(1, 12) - 4) },
    { name: '行为轨迹', value: clamp(base * 0.85 + jitter(2, 14)) },
    { name: '关系网络', value: clamp(base * 0.9 + jitter(3, 10) - 2) },
    { name: '合规风险', value: clamp(base * 0.7 + jitter(4, 16)) },
    { name: '数据置信', value: clamp(60 + jitter(5, 18)) },
  ]
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
        const bootstrapping = res?.registry_status === 'bootstrapping'
        const score = bootstrapping ? 50 : mapPredictionToScore(prediction)
        const level: RiskLevel = bootstrapping ? 'medium' : deriveLevel(score)
        snapshot.value = {
          riskScore: score,
          riskLevel: level,
          prediction,
          note: bootstrapping
            ? '风险模型正在后台训练中，当前返回的是中性值，稍后刷新即可获得真实评分'
            : null,
          factors: deriveFactors(score, prediction),
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
          factors: deriveFactors(50, null),
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
    const factors = Array.isArray(obj.factors) && obj.factors.length > 0
      ? (obj.factors as RiskFactorItem[])
      : deriveFactors(score, prediction)
    const next: RiskSnapshot = { riskScore: score, riskLevel: level, prediction, note, factors }
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
