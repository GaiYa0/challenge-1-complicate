<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCaseStore } from '../store/case'
import { enqueueAnalyzeJob } from '../api/analyze'
import { getFilePreview, getFileAnomaly, listDbFiles } from '../api/file'
import { useTaskPoller } from '../composables/useTaskPoller'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import AnalysisProgress from '../components/investigation/AnalysisProgress.vue'
import StatCard from '../components/investigation/StatCard.vue'
import { notifyError } from '../utils/notify'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const caseId = computed(() => Number(route.params.caseId))

const files = ref<string[]>([])
const taskIds = ref<string[]>([])
const phase = ref<'idle' | 'running' | 'done'>('idle')

// Results
const dataOverview = ref<{ rows: number; cols: number } | null>(null)
const anomalyCount = ref<number | null>(null)
const cleanBefore = ref<number | null>(null)
const cleanAfter = ref<number | null>(null)

const { isPolling, progress, start: startPoll } = useTaskPoller({
  taskIds,
  intervalMs: 2500,
  onAllComplete: () => fetchSummary(),
})

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  // Check if we already have results
  const cached = caseStore.getAnalysis(caseId.value)
  if (cached) {
    dataOverview.value = (cached.dataOverview as { rows: number; cols: number }) ?? null
    anomalyCount.value = (cached.anomalyCount as number) ?? null
    cleanBefore.value = (cached.cleanBefore as number) ?? null
    cleanAfter.value = (cached.cleanAfter as number) ?? null
    phase.value = 'done'
  }
  await loadFiles()
})

async function loadFiles() {
  try {
    const all = (await listDbFiles()) as unknown as { filename: string }[]
    files.value = all.map((f) => f.filename)
  } catch {
    files.value = []
  }
}

async function handleStartAnalysis() {
  if (files.value.length === 0) return
  phase.value = 'running'
  const ids: string[] = []
  const kinds = ['basic', 'iforest', 'graph', 'clean'] as const
  try {
    for (const filename of files.value) {
      for (const kind of kinds) {
        const res = (await enqueueAnalyzeJob(kind, filename)) as unknown as { task_id: string }
        ids.push(res.task_id)
      }
    }
    taskIds.value = ids
    startPoll()
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '启动分析失败')
    phase.value = 'idle'
  }
}

async function fetchSummary() {
  const filename = files.value[0]
  if (!filename) { phase.value = 'done'; return }
  try {
    const [preview, anomaly] = await Promise.allSettled([
      getFilePreview(filename),
      getFileAnomaly(filename),
    ])
    if (preview.status === 'fulfilled') {
      const p = preview.value as unknown as { shape: [number, number] }
      dataOverview.value = { rows: p.shape[0], cols: p.shape[1] }
    }
    if (anomaly.status === 'fulfilled') {
      const a = anomaly.value as unknown as { anomaly_count: number }
      anomalyCount.value = a.anomaly_count
    }
  } catch { /* best effort */ }
  // Cache results
  caseStore.saveAnalysis(caseId.value, {
    dataOverview: dataOverview.value,
    anomalyCount: anomalyCount.value,
    cleanBefore: cleanBefore.value,
    cleanAfter: cleanAfter.value,
  })
  phase.value = 'done'
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
          v-if="dataOverview"
          label="数据概况"
          :value="`${dataOverview.rows} 行 / ${dataOverview.cols} 列`"
          icon="&#128202;"
        />
        <StatCard
          v-if="anomalyCount !== null"
          label="异常检测"
          :value="`发现 ${anomalyCount} 条异常`"
          icon="&#9888;"
          :danger="anomalyCount > 0"
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
