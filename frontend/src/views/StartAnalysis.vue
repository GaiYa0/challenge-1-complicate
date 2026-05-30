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
import { getFieldLabel } from '../utils/fieldLabels'
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

const STATUS_ORDER: Record<string, number> = {
  anomaly: 0,
  pending: 1,
  normal: 2,
}

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
const detailDialogVisible = ref(false)
const currentDetailRow = ref<CleanRow | null>(null)
const expandedRowKeys = ref<string[]>([])

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
    await generateCleanRows()
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
  await analysisStore.fetchFiles(`case-${caseId.value}`)
  if (phase.value === 'done') {
    await generateCleanRows()
  }
})

function generateCleanRows() {
  return loadRealCleanRows()
}

async function loadRealCleanRows() {
  const memo = new Map<number, { markedEvidence: boolean; remark: string }>()
  for (const row of cleanRows.value) {
    memo.set(row.index, { markedEvidence: row.markedEvidence, remark: row.remark })
  }
  const sourceName = files.value.find((f) => !f.startsWith('clean_') && !f.startsWith('feature_')) ?? files.value[0]
  if (!sourceName) {
    cleanRows.value = []
    return
  }
  try {
    const data = await analysisStore.loadCleanRows(sourceName, { offset: 0, limit: 200 })
    cleanRows.value = (data.rows ?? [])
      .map((r) => {
        const old = memo.get(r.index)
        return {
          index: Number(r.index),
          status: (r.status as RowStatus) ?? 'normal',
          markedEvidence: old?.markedEvidence ?? false,
          remark: old?.remark ?? '',
          data: (r.data ?? {}) as Record<string, unknown>,
        }
      })
      .sort((a, b) => {
        const sa = STATUS_ORDER[a.status] ?? 99
        const sb = STATUS_ORDER[b.status] ?? 99
        if (sa !== sb) return sa - sb
        return a.index - b.index
      })
    summary.value = {
      ...summary.value,
      cleanBefore: Number(data.rows_before ?? summary.value.cleanBefore ?? 0),
      cleanAfter: Number(data.rows_after ?? summary.value.cleanAfter ?? 0),
      dataOverview:
        summary.value.dataOverview ??
        (Number.isFinite(Number(data.total))
          ? { rows: Number(data.total), cols: Number(Object.keys(cleanRows.value[0]?.data ?? {}).length) }
          : null),
    }
  } catch (e) {
    cleanRows.value = []
    notifyError(e instanceof Error ? e.message : '加载清洗明细失败')
  }
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

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

function openDetail(row: CleanRow) {
  currentDetailRow.value = row
  detailDialogVisible.value = true
}

function handleRowDblClick(row: CleanRow) {
  const key = String(row.index)
  expandedRowKeys.value = expandedRowKeys.value[0] === key ? [] : [key]
}

function handleExpandChange(row: CleanRow, expandedRows: CleanRow[]) {
  if (!expandedRows.length) {
    expandedRowKeys.value = []
    return
  }
  const currentKey = String(row.index)
  if (expandedRowKeys.value[0] !== currentKey) {
    expandedRowKeys.value = [currentKey]
  }
}

function closeDetail() {
  detailDialogVisible.value = false
  currentDetailRow.value = null
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

function summarizeRowData(data: Record<string, unknown>): string {
  const entries = Object.entries(data ?? {}).filter(([, v]) => v !== null && v !== undefined && `${v}` !== '')
  if (!entries.length) return '（空记录）'
  return entries
    .slice(0, 2)
    .map(([k, v]) => `${getFieldLabel(k)}: ${formatDetailValue(v)}`)
    .join(' | ')
}

const anomalyRows = computed(() => cleanRows.value.filter((r) => r.status === 'anomaly'))
const pendingRows = computed(() => cleanRows.value.filter((r) => r.status === 'pending'))
const normalRows = computed(() => cleanRows.value.filter((r) => r.status === 'normal'))
const evidenceRows = computed(() => cleanRows.value.filter((r) => r.markedEvidence))
const detailEntries = computed(() =>
  Object.entries(currentDetailRow.value?.data ?? {}).map(([key, value]) => ({
    label: getFieldLabel(key),
    value: formatDetailValue(value),
  })),
)

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
          row-key="index"
          :expand-row-keys="expandedRowKeys"
          max-height="520"
          size="small"
          stripe
          border
          :row-class-name="({ row }: { row: CleanRow }) => `row-clickable row-${row.status}${row.markedEvidence ? ' row-evidence' : ''}`"
          @row-dblclick="handleRowDblClick"
          @expand-change="handleExpandChange"
        >
          <el-table-column type="expand" width="40" align="center">
            <template #default="{ row }">
              <div class="inline-action-row">
                <span class="inline-action-label">双击行后可在此执行操作</span>
                <el-button type="primary" size="small" @click.stop="openDetail(row)">查看详情</el-button>
              </div>
            </template>
          </el-table-column>
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
              <div class="detail-text">
                <span>{{ summarizeRowData(row.data) }}</span>
                <span class="detail-link-hint">双击展开操作</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="证据" width="90" align="center">
            <template #default="{ row }">
              <el-button
                :type="row.markedEvidence ? 'warning' : 'default'"
                size="small"
                plain
                @click.stop="toggleEvidence(row)"
                @dblclick.stop
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
                @click.stop="openRemark(row)"
                @dblclick.stop
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

    <el-dialog
      v-model="detailDialogVisible"
      title="数据项详情"
      width="640px"
      :close-on-click-modal="false"
      @closed="closeDetail"
    >
      <template v-if="currentDetailRow">
        <div class="detail-meta">
          <el-tag effect="plain">序号 {{ currentDetailRow.index }}</el-tag>
          <el-tag :color="statusColor(currentDetailRow.status)" effect="dark" style="border:none; color:#fff">
            {{ statusLabel(currentDetailRow.status) }}
          </el-tag>
          <el-tag v-if="currentDetailRow.markedEvidence" type="warning" effect="plain">已标记证据</el-tag>
          <el-tag v-if="currentDetailRow.remark" type="success" effect="plain">已备注</el-tag>
        </div>
        <div v-if="currentDetailRow.remark" class="detail-remark">
          备注：{{ currentDetailRow.remark }}
        </div>
        <el-table :data="detailEntries" size="small" border stripe max-height="360">
          <el-table-column prop="label" label="字段" min-width="180" />
          <el-table-column prop="value" label="值" min-width="280">
            <template #default="{ row }">
              <pre class="detail-value">{{ row.value }}</pre>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button type="primary" @click="closeDetail">关闭</el-button>
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
.detail-text {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: inherit;
  text-align: left;
  padding: 2px 0;
}
:deep(.el-table__expanded-cell) {
  background: var(--app-bg-card);
}
.inline-action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 4px;
}
.inline-action-label {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.detail-link-hint {
  font-size: 12px;
  color: var(--app-primary);
  opacity: 0;
  transition: opacity 0.16s ease;
  white-space: nowrap;
}
.detail-text .detail-link-hint {
  pointer-events: none;
}
:deep(.row-clickable) {
  cursor: pointer;
}
:deep(.row-clickable:hover > td) {
  background: color-mix(in srgb, var(--app-primary) 6%, transparent);
}
:deep(.row-clickable:hover .detail-link-hint) {
  opacity: 1;
}
.detail-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.detail-remark {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0 0 10px;
}
.detail-value {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
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
