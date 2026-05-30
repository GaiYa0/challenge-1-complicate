<script setup lang="ts">
/**
 * 证据报告 — 以证据为核心的调查报告
 * 结构：嫌疑人信息 → 关键行为 → 证据链（时间排序） → 关联人影响 → 结论
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useCaseStore } from '../store/case'
import { useAnalysisStore } from '../store/modules/analysis.store'
import { useFileStore } from '../store/modules/file.store'
import { useClueStore } from '../store/modules/clue.store'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import ReportSection from '../components/investigation/ReportSection.vue'
import StatusTag from '../components/common/StatusTag.vue'
import FormatTime from '../components/common/FormatTime.vue'
import CountUp from '../components/common/CountUp.vue'
import { notifySuccess, notifyError } from '../utils/notify'
import { formatDateTime } from '../utils/format'
import { ACTION_TYPE_LABELS } from '../types/evidence'
import type { ActionType } from '../types/evidence'
import { generateReport, getReportTask } from '../api/reports'

const route = useRoute()
const caseStore = useCaseStore()
const analysisStore = useAnalysisStore()
const fileStore = useFileStore()
const clueStore = useClueStore()

const caseId = computed(() => Number(route.params.caseId))
const caseInfo = computed(() => caseStore.currentCase)
const hasData = computed(() => fileStore.items.length > 0)

const hydrating = ref(false)
const generatedAt = ref('')

const analysis = computed(() => caseStore.getAnalysis(caseId.value))
const fileCount = computed(() => fileStore.items.length)

const anomalyCount = computed<number>(() => {
  const v = Number(analysis.value?.anomalyCount)
  return Number.isFinite(v) ? v : 0
})
const rowsCount = computed<number>(() => {
  const d = analysis.value?.dataOverview as { rows?: number } | undefined
  return Number.isFinite(Number(d?.rows)) ? Number(d?.rows) : 0
})

const cluesByCategory = computed(() => {
  const map: Record<string, typeof clueStore.clueList> = {}
  for (const c of clueStore.clueList) {
    const cat = c.category || 'other'
    if (!map[cat]) map[cat] = []
    map[cat].push(c)
  }
  return map
})

async function hydrateFromBackend() {
  hydrating.value = true
  try {
    if (!caseStore.currentCase || caseStore.currentCase.id !== caseId.value) {
      try { await caseStore.fetchCases(caseStore.page) } catch { /* */ }
    }
    caseStore.selectCase(caseId.value)
    if (fileStore.items.length === 0) {
      await fileStore.fetchList(`case-${caseId.value}`)
    }
    if (!analysis.value && hasData.value) {
      await analysisStore.fetchFiles(`case-${caseId.value}`)
      const srcName = analysisStore.files.find((f) => !f.startsWith('clean_') && !f.startsWith('feature_'))
      if (srcName) {
        const summary = await analysisStore.loadSummary(srcName)
        caseStore.saveAnalysis(caseId.value, { ...summary })
      }
    }
    if (hasData.value) {
      await clueStore.fetchList(caseId.value)
    }
    generatedAt.value = formatDateTime(Date.now(), 'YYYY-MM-DD HH:mm')
  } finally {
    hydrating.value = false
  }
}

onMounted(() => void hydrateFromBackend())
watch(caseId, (id, prev) => { if (id !== prev) void hydrateFromBackend() })

const completing = ref(false)
const exporting = ref(false)
async function handleComplete() {
  completing.value = true
  try {
    await caseStore.completeCase(caseId.value)
    notifySuccess('案件已标记为完成')
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '操作失败')
  } finally {
    completing.value = false
  }
}

function handlePrint() {
  window.print()
}

async function resolveReportPersonId(): Promise<string | null> {
  const q = String(route.query.personId || '').trim()
  if (q) return q
  const top = clueStore.clueList[0]
  if (!top?.id) return null
  const detail = await clueStore.fetchDetail(top.id)
  return detail?.person_id ? String(detail.person_id).trim() : null
}

async function pollReportTask(taskId: string, timeoutMs = 180000): Promise<string> {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const status = await getReportTask(taskId)
    if (status.status === 'SUCCESS' && status.result?.download_url) {
      return status.result.download_url
    }
    if (status.status === 'FAILURE') {
      throw new Error(status.error || '导出失败')
    }
    await new Promise((resolve) => setTimeout(resolve, 1500))
  }
  throw new Error('导出超时，请稍后在任务页查看')
}

async function handleExport(format: 'pdf' | 'docx') {
  exporting.value = true
  try {
    const personId = await resolveReportPersonId()
    if (!personId) throw new Error('未找到可导出对象，请先生成人物线索')
    const queued = await generateReport({
      case_id: caseId.value,
      person_id: personId,
      format,
    })
    const url = await pollReportTask(queued.task_id)
    window.open(url, '_blank', 'noopener')
    notifySuccess(`已生成${format.toUpperCase()}报告`)
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

function categoryLabel(cat: string): string {
  return ACTION_TYPE_LABELS[cat as ActionType] || cat || '其他'
}

const hasAnyData = computed(() => Boolean(analysis.value || caseInfo.value))
</script>

<template>
  <div class="report-page">
    <StepIndicator :current="5" />

    <header class="page-head no-print">
      <div>
        <h1 class="page-title">证据报告</h1>
        <p class="page-subtitle">基于证据链生成的调查报告，可直接打印归档</p>
      </div>
      <el-button text @click="hydrateFromBackend" :loading="hydrating">刷新数据</el-button>
    </header>

    <div v-if="!hasData && !hydrating" class="empty-state">
      <p>当前案件尚未导入数据</p>
      <p class="empty-hint">所有证据报告必须建立在清洗结果之上，请先导入数据</p>
    </div>

    <el-skeleton v-else-if="hydrating && !hasAnyData" :rows="8" animated />

    <div v-else class="report-document" id="report-document">
      <div class="report-header-block">
        <h2 class="report-doc-title">证据分析报告</h2>
        <p class="report-meta">
          <span v-if="caseInfo?.case_number">案件编号: {{ caseInfo.case_number }} &#183; </span>
          <span>生成时间: {{ generatedAt || '--' }}</span>
        </p>
      </div>

      <ReportSection title="一、嫌疑人信息">
        <table class="info-table" v-if="caseInfo">
          <tr><td class="info-label">案件名称</td><td>{{ caseInfo.name }}</td></tr>
          <tr v-if="caseInfo.case_number"><td class="info-label">案件编号</td><td>{{ caseInfo.case_number }}</td></tr>
          <tr><td class="info-label">创建日期</td>
            <td><FormatTime :value="caseInfo.created_at" :show-relative="false" /></td></tr>
          <tr><td class="info-label">当前状态</td>
            <td><StatusTag :raw="caseInfo.status" size="small" effect="light" /></td></tr>
          <tr v-if="caseInfo.note"><td class="info-label">备注</td><td>{{ caseInfo.note }}</td></tr>
        </table>
        <p v-else class="no-data">案件信息尚未加载</p>
      </ReportSection>

      <ReportSection title="二、关键行为列表">
        <div v-if="clueStore.clueList.length > 0">
          <div v-for="(clues, cat) in cluesByCategory" :key="cat" class="behavior-group">
            <h4 class="behavior-cat">{{ categoryLabel(cat) }}（{{ clues.length }} 项）</h4>
            <ul class="behavior-list">
              <li v-for="c in clues" :key="c.id" class="behavior-item">
                <span class="behavior-title">{{ c.title }}</span>
                <el-tag :type="c.risk_level === 'high' ? 'danger' : c.risk_level === 'medium' ? 'warning' : 'info'" size="small" effect="plain">
                  {{ c.risk_level === 'high' ? '高' : c.risk_level === 'medium' ? '中' : '低' }}
                </el-tag>
              </li>
            </ul>
          </div>
        </div>
        <p v-else class="no-data">尚未发现关键行为</p>
      </ReportSection>

      <ReportSection title="三、证据链（按时间排序）">
        <div v-if="clueStore.clueList.length > 0">
          <el-table :data="clueStore.clueList" size="small" stripe border class="evidence-report-table">
            <el-table-column prop="title" label="证据描述" min-width="240" show-overflow-tooltip />
            <el-table-column label="类别" width="100">
              <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
            </el-table-column>
            <el-table-column label="等级" width="80" align="center">
              <template #default="{ row }">
                <StatusTag :raw="row.risk_level" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="评分" width="80" align="center">
              <template #default="{ row }">{{ row.risk_score?.toFixed(0) ?? '--' }}</template>
            </el-table-column>
          </el-table>
        </div>
        <p v-else class="no-data">暂无证据链数据</p>
      </ReportSection>

      <ReportSection title="四、数据清洗概况">
        <div v-if="analysis?.dataOverview" class="stat-row">
          <div class="stat-cell">
            <span class="stat-value"><CountUp :value="rowsCount" /></span>
            <span class="stat-label">清洗后有效行数</span>
          </div>
          <div class="stat-cell">
            <span class="stat-value"><CountUp :value="anomalyCount" /></span>
            <span class="stat-label">异常记录数</span>
          </div>
          <div class="stat-cell">
            <span class="stat-value"><CountUp :value="fileCount" /></span>
            <span class="stat-label">数据文件</span>
          </div>
        </div>
        <p v-else class="no-data">尚未完成数据清洗</p>
      </ReportSection>

      <ReportSection title="五、结论（基于证据）">
        <div v-if="clueStore.clueList.length > 0" class="conclusion">
          <p>
            基于数据清洗和证据链分析，本案件共发现
            <strong>{{ clueStore.clueList.length }}</strong> 项关键行为证据，
            涵盖 <strong>{{ Object.keys(cluesByCategory).length }}</strong> 个类别。
          </p>
          <p v-if="clueStore.clueList.filter(c => c.risk_level === 'high').length > 0" class="conclusion-highlight">
            其中 <strong>{{ clueStore.clueList.filter(c => c.risk_level === 'high').length }}</strong> 项为高风险证据，
            需重点关注并结合原始记录做进一步定性分析。
          </p>
          <p v-else>
            当前证据中未发现高风险项，建议结合其他调查渠道补充取证。
          </p>
        </div>
        <p v-else class="no-data">证据不足，暂无法得出结论。建议补充数据后重新分析。</p>
      </ReportSection>

      <ReportSection title="六、数据来源清单">
        <ol v-if="fileStore.items.length > 0" class="file-evidence">
          <li v-for="f in fileStore.items" :key="f.filename">
            {{ f.filename }}
            <span v-if="f.upload_time" class="evidence-time">
              （导入: <FormatTime :value="f.upload_time" :show-relative="false" />）
            </span>
          </li>
        </ol>
        <p v-else class="no-data">尚无导入数据</p>
      </ReportSection>

      <div class="report-footer">
        <p class="sig-line">制表: 检察调查辅助系统 &#183; 打印日期: {{ generatedAt || '--' }}</p>
      </div>
    </div>

    <div v-if="hasData" class="report-actions no-print">
      <el-button size="large" @click="handlePrint" :disabled="!hasAnyData">打印 / 导出 PDF</el-button>
      <el-button size="large" :loading="exporting" :disabled="!hasAnyData" @click="handleExport('pdf')">正式导出 PDF</el-button>
      <el-button size="large" :loading="exporting" :disabled="!hasAnyData" @click="handleExport('docx')">正式导出 Word</el-button>
      <el-button
        type="primary"
        size="large"
        :loading="completing"
        @click="handleComplete"
        :disabled="caseInfo?.status === 'completed'"
      >
        {{ caseInfo?.status === 'completed' ? '案件已完成' : '标记案件完成' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.report-page { max-width: 860px; margin: 0 auto; }
.page-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 16px;
}
.page-title { font-size: 22px; font-weight: 700; color: var(--app-text); margin: 0 0 4px; }
.page-subtitle { font-size: 14px; color: var(--app-text-secondary); margin: 0; }
.report-document {
  background: var(--app-bg-card); border: 1px solid var(--app-border);
  border-radius: var(--app-radius); padding: 40px 48px;
  max-width: 820px; margin: 0 auto; box-shadow: var(--app-shadow-card);
}
.report-header-block {
  text-align: center; margin-bottom: 32px; padding-bottom: 16px;
  border-bottom: 2px solid var(--app-text);
}
.report-doc-title { font-size: 24px; font-weight: 700; color: var(--app-text); margin: 0 0 8px; }
.report-meta { font-size: 13px; color: var(--app-text-secondary); margin: 0; }
.info-table { width: 100%; border-collapse: collapse; }
.info-table td { padding: 8px 12px; border-bottom: 1px solid var(--app-border); font-size: 15px; color: var(--app-text); }
.info-label { width: 120px; color: var(--app-text-secondary); font-weight: 500; }
.behavior-group { margin-bottom: 16px; }
.behavior-cat { font-size: 14px; font-weight: 600; color: var(--app-text); margin: 0 0 8px; }
.behavior-list { margin: 0; padding-left: 20px; }
.behavior-item { margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
.behavior-title { font-size: 14px; color: var(--app-text); }
.evidence-report-table { margin-top: 12px; }
.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.stat-cell {
  background: var(--app-bg-layout); border-radius: var(--app-radius);
  padding: 18px 20px; text-align: center;
}
.stat-value {
  display: block; font-size: 26px; font-weight: 700; color: var(--app-primary);
  line-height: 1.2; margin-bottom: 4px; font-variant-numeric: tabular-nums;
}
.stat-label { font-size: 13px; color: var(--app-text-secondary); }
.conclusion { line-height: 1.8; font-size: 15px; color: var(--app-text); }
.conclusion-highlight { color: #dc2626; font-weight: 500; }
.no-data { color: var(--app-text-secondary); font-style: italic; }
.file-evidence { padding-left: 20px; margin: 0; }
.file-evidence li { margin-bottom: 6px; font-size: 14px; }
.evidence-time { color: var(--app-text-secondary); font-size: 12px; }
.report-footer {
  margin-top: 32px; padding-top: 16px;
  border-top: 1px solid var(--app-border); text-align: right;
}
.sig-line { font-size: 12px; color: var(--app-text-secondary); margin: 0; }
.report-actions {
  display: flex; justify-content: center; gap: 16px;
  margin-top: 32px; padding-bottom: 24px;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 8px; }
.empty-hint { font-size: 13px !important; margin-bottom: 20px !important; }
@media print {
  .report-document { page-break-inside: avoid; padding: 0 !important; border: none !important; box-shadow: none !important; }
}
</style>
