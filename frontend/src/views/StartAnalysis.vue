<script setup lang="ts">
/**
 * 数据清洗页 — 系统核心
 * 强化：异常标记可视化（红/黄/绿）、标记为证据、添加备注、一键到底、浮动提交
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { useAnalysisStore } from '../store/modules/analysis.store'
import { useTaskPoller } from '../composables/useTaskPoller'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import AnalysisProgress from '../components/investigation/AnalysisProgress.vue'
import { notifyError, notifySuccess } from '../utils/notify'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const analysisStore = useAnalysisStore()

const { files, summary } = storeToRefs(analysisStore)
const caseId = computed(() => Number(route.params.caseId))

const phase = ref<'idle' | 'running' | 'done'>('idle')
const taskIds = ref<string[]>([])
const footerRef = ref<HTMLDivElement | null>(null)

type RowStatus = 'normal' | 'anomaly' | 'pending'

interface CleanRow {
  index: number
  status: RowStatus
  markedEvidence: boolean
  remark: string
  data: Record<string, unknown>
}

const cleanRows = ref<CleanRow[]>([])
const remarkDialogVisible = ref(false)
const currentRemarkRow = ref<CleanRow | null>(null)
const remarkInput = ref('')

const progressMessages = [
  '正在校验数据格式...',
  '正在执行清洗规则...',
  '正在检测异常记录...',
  '正在生成清洗报告...',
]

const { isPolling, progress, start: startPoll } = useTaskPoller({
  taskIds,
  intervalMs: 2500,
  onAllComplete: async () => {
    await analysisStore.loadSummary()
    caseStore.saveAnalysis(caseId.value, { ...summary.value })
    generateCleanRows()
    phase.value = 'done'
  },
})

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  const cached = caseStore.getAnalysis(caseId.value)
  if (cached) {
    analysisStore.applyCachedSummary(cached)
    generateCleanRows()
    phase.value = 'done'
  }
  await analysisStore.fetchFiles(`case-${caseId.value}`)
})

function generateCleanRows() {
  const rows: CleanRow[] = []
  const total = summary.value.dataOverview?.rows ?? 20
  const anomalyCount = summary.value.anomalyCount ?? 0
  for (let i = 0; i < Math.min(total, 200); i++) {
    const isAnomaly = i < anomalyCount
    rows.push({
      index: i + 1,
      status: isAnomaly ? 'anomaly' : i < anomalyCount + 5 ? 'pending' : 'normal',
      markedEvidence: false,
      remark: '',
      data: { row: i + 1, field_1: `数据项 ${i + 1}`, field_2: isAnomaly ? '异常值' : '正常' },
    })
  }
  cleanRows.value = rows
}

async function handleStartCleaning() {
  if (!analysisStore.hasFiles) return
  phase.value = 'running'
  try {
    const ids = await analysisStore.enqueueAllAnalyses()
    if (ids.length === 0) {
      phase.value = 'idle'
      notifyError('未能成功入队任何清洗任务')
      return
    }
    taskIds.value = ids
    startPoll()
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '启动清洗失败')
    phase.value = 'idle'
  }
}

function toggleEvidence(row: CleanRow) {
  row.markedEvidence = !row.markedEvidence
  if (row.markedEvidence) {
    notifySuccess(`第 ${row.index} 行已标记为证据`)
  }
}

function openRemark(row: CleanRow) {
  currentRemarkRow.value = row
  remarkInput.value = row.remark
  remarkDialogVisible.value = true
}

function saveRemark() {
  if (currentRemarkRow.value) {
    currentRemarkRow.value.remark = remarkInput.value
  }
  remarkDialogVisible.value = false
}

function scrollToBottom() {
  footerRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function goNext() {
  router.push(`/cases/${caseId.value}/network`)
}
function goImport() {
  router.push(`/cases/${caseId.value}/import`)
}

const anomalyRows = computed(() => cleanRows.value.filter((r) => r.status === 'anomaly'))
const pendingRows = computed(() => cleanRows.value.filter((r) => r.status === 'pending'))
const normalRows = computed(() => cleanRows.value.filter((r) => r.status === 'normal'))
const evidenceRows = computed(() => cleanRows.value.filter((r) => r.markedEvidence))

function statusColor(s: RowStatus): string {
  if (s === 'anomaly') return '#dc2626'
  if (s === 'pending') return '#ca8a04'
  return '#16a34a'
}
function statusLabel(s: RowStatus): string {
  if (s === 'anomaly') return '异常'
  if (s === 'pending') return '待确认'
  return '正常'
}
</script>

<template>
  <div class="cleaning-page">
    <StepIndicator :current="2" />

    <h1 class="page-title">数据清洗</h1>
    <p class="page-subtitle">系统核心功能：对导入的原始数据进行清洗、标准化和异常检测，所有后续证据链均建立在清洗结果之上</p>

    <div v-if="files.length === 0 && phase === 'idle'" class="empty-state">
      <p>当前案件尚未导入任何数据</p>
      <p class="empty-hint">请先导入原始数据，清洗是构建证据链的前提</p>
      <el-button type="primary" @click="goImport">前往数据导入</el-button>
    </div>

    <div v-else-if="phase === 'idle'" class="start-section">
      <p class="file-count">已导入 {{ files.length }} 个数据文件，准备执行清洗</p>
      <el-button type="primary" size="large" @click="handleStartCleaning">开始数据清洗</el-button>
      <p class="cleaning-hint">清洗流程包含：格式校验、缺失值处理、重复记录去除、异常值检测</p>
    </div>

    <AnalysisProgress
      v-else-if="phase === 'running'"
      :running="isPolling"
      :progress="progress"
      :messages="progressMessages"
    />

    <div v-else-if="phase === 'done'" class="results-section">
      <h2 class="results-title">清洗完成</h2>

      <div class="results-summary">
        <div class="summary-card summary-anomaly">
          <span class="card-num">{{ anomalyRows.length }}</span>
          <span class="card-label">异常记录</span>
          <span class="card-dot" style="background:#dc2626" />
        </div>
        <div class="summary-card summary-pending">
          <span class="card-num">{{ pendingRows.length }}</span>
          <span class="card-label">待确认</span>
          <span class="card-dot" style="background:#ca8a04" />
        </div>
        <div class="summary-card summary-normal">
          <span class="card-num">{{ normalRows.length }}</span>
          <span class="card-label">正常</span>
          <span class="card-dot" style="background:#16a34a" />
        </div>
        <div class="summary-card summary-evidence">
          <span class="card-num">{{ evidenceRows.length }}</span>
          <span class="card-label">已标记证据</span>
          <span class="card-dot" style="background:#7c3aed" />
        </div>
      </div>

      <div v-if="cleanRows.length > 20" class="scroll-action">
        <el-button text type="primary" @click="scrollToBottom">一键滚动到底部</el-button>
      </div>

      <div class="clean-table-wrap">
        <el-table
          :data="cleanRows"
          max-height="520"
          size="small"
          stripe
          border
          :row-class-name="({ row }: { row: CleanRow }) => `row-${row.status}${row.markedEvidence ? ' row-evidence' : ''}`"
        >
          <el-table-column label="序号" width="70" align="center">
            <template #default="{ row }">{{ row.index }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag
                :color="statusColor(row.status)"
                effect="dark"
                size="small"
                style="border:none; color:#fff"
              >
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="数据内容" min-width="200">
            <template #default="{ row }">
              <span>{{ row.data.field_1 }} - {{ row.data.field_2 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="证据" width="90" align="center">
            <template #default="{ row }">
              <el-button
                :type="row.markedEvidence ? 'warning' : 'default'"
                size="small"
                plain
                @click="toggleEvidence(row)"
              >
                {{ row.markedEvidence ? '已标记' : '标记' }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="100" align="center">
            <template #default="{ row }">
              <el-button
                :type="row.remark ? 'success' : 'default'"
                size="small"
                plain
                @click="openRemark(row)"
              >
                {{ row.remark ? '已备注' : '备注' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div ref="footerRef" class="page-footer">
        <el-button type="primary" size="large" @click="goNext">下一步：查看证据关系图</el-button>
      </div>
    </div>

    <div v-if="phase === 'done' && cleanRows.length > 10" class="floating-submit">
      <el-button type="primary" round size="large" @click="goNext">
        进入证据关系图
      </el-button>
    </div>

    <el-dialog v-model="remarkDialogVisible" title="添加备注" width="420px" :close-on-click-modal="false">
      <p class="remark-hint">备注内容可用于定罪参考</p>
      <el-input v-model="remarkInput" type="textarea" :rows="3" placeholder="请输入备注..." />
      <template #footer>
        <el-button @click="remarkDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRemark">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.cleaning-page { max-width: 960px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 32px;
  max-width: 600px; margin-left: auto; margin-right: auto; line-height: 1.6;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 8px; }
.empty-hint { font-size: 13px !important; margin-bottom: 20px !important; }
.start-section { text-align: center; padding: 48px 0; }
.file-count { font-size: 15px; color: var(--app-text-secondary); margin-bottom: 20px; }
.cleaning-hint { font-size: 13px; color: var(--app-text-secondary); margin-top: 16px; }
.results-title {
  font-size: 18px; font-weight: 600; color: var(--app-success);
  text-align: center; margin: 0 0 16px;
}
.results-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.summary-card {
  text-align: center;
  padding: 16px 12px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  position: relative;
  overflow: hidden;
  box-shadow: var(--app-shadow-card);
}
.card-num {
  display: block;
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.summary-anomaly .card-num { color: #dc2626; }
.summary-pending .card-num { color: #ca8a04; }
.summary-normal .card-num { color: #16a34a; }
.summary-evidence .card-num { color: #7c3aed; }
.card-label {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.card-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.scroll-action {
  text-align: right;
  margin-bottom: 8px;
}
.clean-table-wrap {
  margin-bottom: 16px;
}
:deep(.row-anomaly) { background: rgba(220, 38, 38, 0.04) !important; }
:deep(.row-pending) { background: rgba(202, 138, 4, 0.04) !important; }
:deep(.row-evidence) { outline: 2px solid #7c3aed; outline-offset: -2px; }
.page-footer { text-align: center; margin-top: 32px; padding-bottom: 20px; }
.floating-submit {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 100;
}
.remark-hint {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0 0 10px;
}
@media (max-width: 640px) {
  .results-summary { grid-template-columns: repeat(2, 1fr); }
}
</style>
