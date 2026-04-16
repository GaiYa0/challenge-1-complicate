<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { useAnalysisStore } from '../store/modules/analysis.store'
import { useTaskPoller } from '../composables/useTaskPoller'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import AnalysisProgress from '../components/investigation/AnalysisProgress.vue'
import StatCard from '../components/investigation/StatCard.vue'
import { notifyError } from '../utils/notify'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const analysisStore = useAnalysisStore()

const { files, summary } = storeToRefs(analysisStore)
const caseId = computed(() => Number(route.params.caseId))

const phase = ref<'idle' | 'running' | 'done'>('idle')
const taskIds = ref<string[]>([])

const { isPolling, progress, start: startPoll } = useTaskPoller({
  taskIds,
  intervalMs: 2500,
  onAllComplete: async () => {
    await analysisStore.loadSummary()
    caseStore.saveAnalysis(caseId.value, { ...summary.value })
    phase.value = 'done'
  },
})

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  const cached = caseStore.getAnalysis(caseId.value)
  if (cached) {
    analysisStore.applyCachedSummary(cached)
    phase.value = 'done'
  }
  await analysisStore.fetchFiles()
})

async function handleStartAnalysis() {
  if (!analysisStore.hasFiles) return
  phase.value = 'running'
  try {
    const ids = await analysisStore.enqueueAllAnalyses()
    if (ids.length === 0) {
      phase.value = 'idle'
      notifyError('未能成功入队任何分析任务')
      return
    }
    taskIds.value = ids
    startPoll()
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '启动分析失败')
    phase.value = 'idle'
  }
}

function goNext() {
  router.push(`/cases/${caseId.value}/network`)
}
function goImport() {
  router.push(`/cases/${caseId.value}/import`)
}
</script>

<template>
  <div class="analysis-page">
    <StepIndicator :current="2" />

    <h1 class="page-title">数据分析</h1>
    <p class="page-subtitle">系统将自动对导入的数据进行全面分析</p>

    <div v-if="files.length === 0 && phase === 'idle'" class="empty-state">
      <p>请先导入数据</p>
      <el-button type="primary" @click="goImport">去导入数据 &rarr;</el-button>
    </div>

    <div v-else-if="phase === 'idle'" class="start-section">
      <p class="file-count">已导入 {{ files.length }} 个数据文件</p>
      <el-button type="primary" size="large" @click="handleStartAnalysis">开始分析</el-button>
    </div>

    <AnalysisProgress v-else-if="phase === 'running'" :running="isPolling" :progress="progress" />

    <div v-else-if="phase === 'done'" class="results-section">
      <h2 class="results-title">分析完成</h2>
      <div class="results-grid">
        <StatCard
          v-if="summary.dataOverview"
          label="数据概况"
          :value="`${summary.dataOverview.rows} 行 / ${summary.dataOverview.cols} 列`"
          icon="&#128202;"
        />
        <StatCard
          v-if="summary.anomalyCount !== null"
          label="异常检测"
          :value="`发现 ${summary.anomalyCount} 条异常`"
          icon="&#9888;"
          :danger="summary.anomalyCount > 0"
        />
      </div>
      <div class="page-footer">
        <el-button type="primary" size="large" @click="goNext">下一步：查看关系网络 &rarr;</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis-page { max-width: 800px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 32px;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 16px; }
.start-section { text-align: center; padding: 48px 0; }
.file-count { font-size: 15px; color: var(--app-text-secondary); margin-bottom: 20px; }
.results-title {
  font-size: 18px; font-weight: 600; color: var(--app-success);
  text-align: center; margin: 0 0 24px;
}
.results-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px; margin-bottom: 16px;
}
.page-footer { text-align: center; margin-top: 32px; }
</style>
