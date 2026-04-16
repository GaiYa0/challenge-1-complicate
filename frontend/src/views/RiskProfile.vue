<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { useFileStore } from '../store/modules/file.store'
import { useRiskStore } from '../store/modules/risk.store'
import { useTaskPoller } from '../composables/useTaskPoller'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import AnalysisProgress from '../components/investigation/AnalysisProgress.vue'
import RiskScoreGauge from '../components/investigation/RiskScoreGauge.vue'
import StatCard from '../components/investigation/StatCard.vue'
import { notifyError } from '../utils/notify'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const fileStore = useFileStore()
const riskStore = useRiskStore()

const { snapshot } = storeToRefs(riskStore)

const caseId = computed(() => Number(route.params.caseId))
const phase = ref<'idle' | 'running' | 'done'>('idle')
const taskIds = ref<string[]>([])

const progressMessages = [
  '正在提取关键信息...',
  '正在评估风险因素...',
  '正在计算风险评分...',
  '正在生成评估结果...',
]

const { isPolling, progress, start: startPoll } = useTaskPoller({
  taskIds,
  intervalMs: 2500,
  onAllComplete: async () => {
    const names = fileStore.sourceFilenames()
    await riskStore.evaluate(names[0])
    caseStore.saveRisk(caseId.value, { ...snapshot.value })
    phase.value = 'done'
  },
})

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  const cached = caseStore.getRisk(caseId.value)
  if (cached) {
    riskStore.applyCached(cached)
    phase.value = 'done'
  }
  await fileStore.fetchList()
})

const analysisSummary = computed(() => caseStore.getAnalysis(caseId.value))
const anomalyCount = computed(() => {
  const n = Number(analysisSummary.value?.anomalyCount ?? NaN)
  return Number.isFinite(n) ? n : null
})

async function handleStart() {
  const names = fileStore.sourceFilenames()
  if (names.length === 0) return
  phase.value = 'running'
  try {
    const ids = await riskStore.enqueueFeatureJobs(names)
    if (ids.length === 0) {
      phase.value = 'idle'
      notifyError('未能入队任何特征提取任务')
      return
    }
    taskIds.value = ids
    startPoll()
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '启动评估失败')
    phase.value = 'idle'
  }
}

function goNext() {
  router.push(`/cases/${caseId.value}/report`)
}
</script>

<template>
  <div class="risk-page">
    <StepIndicator :current="4" />

    <h1 class="page-title">风险画像</h1>
    <p class="page-subtitle">基于数据分析结果，评估涉案人员的风险等级</p>

    <div v-if="phase === 'idle'" class="start-section">
      <el-button
        type="primary"
        size="large"
        :disabled="fileStore.items.length === 0"
        @click="handleStart"
      >
        开始风险评估
      </el-button>
      <p v-if="fileStore.items.length === 0" class="hint">请先导入并分析数据</p>
    </div>

    <AnalysisProgress
      v-else-if="phase === 'running'"
      :running="isPolling"
      :progress="progress"
      :messages="progressMessages"
    />

    <div v-else-if="phase === 'done'" class="results-section">
      <el-alert
        v-if="snapshot.note"
        class="risk-note"
        :title="snapshot.note"
        type="warning"
        show-icon
        :closable="false"
      />
      <div class="gauge-wrapper">
        <RiskScoreGauge :score="snapshot.riskScore" :level="snapshot.riskLevel" />
      </div>

      <div class="factor-grid">
        <StatCard
          label="数据分析"
          :value="anomalyCount !== null ? `${anomalyCount} 条异常` : '已完成'"
          icon="&#128202;"
          :danger="(anomalyCount ?? 0) > 0"
        />
        <StatCard
          label="风险评分"
          :value="snapshot.riskScore"
          icon="&#128200;"
          :danger="snapshot.riskLevel === 'high'"
        />
      </div>

      <div class="page-footer">
        <el-button type="primary" size="large" @click="goNext">下一步：生成调查报告 &rarr;</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-page { max-width: 800px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 32px;
}
.start-section { text-align: center; padding: 60px 0; }
.hint { font-size: 13px; color: var(--app-text-secondary); margin-top: 12px; }
.risk-note { margin-bottom: 16px; }
.gauge-wrapper { display: flex; justify-content: center; margin-bottom: 32px; }
.factor-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px; margin-bottom: 16px;
}
.page-footer { text-align: center; margin-top: 32px; }
</style>
