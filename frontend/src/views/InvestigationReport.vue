<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useCaseStore } from '../store/case'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import ReportSection from '../components/investigation/ReportSection.vue'
import { notifySuccess } from '../utils/notify'

const route = useRoute()
const caseStore = useCaseStore()
const caseId = computed(() => Number(route.params.caseId))

onMounted(() => {
  caseStore.selectCase(caseId.value)
})

const caseInfo = computed(() => caseStore.currentCase)
const analysis = computed(() => caseStore.getAnalysis(caseId.value))
const risk = computed(() => caseStore.getRisk(caseId.value))

const riskLevelText = computed(() => {
  const level = risk.value?.riskLevel as string | undefined
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中等风险'
  return '低风险'
})

const completing = ref(false)

async function handleComplete() {
  completing.value = true
  try {
    await caseStore.completeCase(caseId.value)
    notifySuccess('案件已标记为完成')
  } finally {
    completing.value = false
  }
}

function handlePrint() {
  window.print()
}
</script>

<template>
  <div class="report-page">
    <StepIndicator :current="5" />

    <h1 class="page-title">调查报告</h1>
    <p class="page-subtitle">汇总本案件的全部分析结果</p>

    <div class="report-document">
      <div class="report-header-block">
        <h2 class="report-doc-title">调查分析报告</h2>
      </div>

      <ReportSection title="案件基本信息">
        <table class="info-table" v-if="caseInfo">
          <tr><td class="info-label">案件名称</td><td>{{ caseInfo.name }}</td></tr>
          <tr v-if="caseInfo.case_number"><td class="info-label">案件编号</td><td>{{ caseInfo.case_number }}</td></tr>
          <tr><td class="info-label">创建日期</td><td>{{ caseInfo.created_at?.slice(0, 10) }}</td></tr>
          <tr><td class="info-label">状态</td><td>{{ caseInfo.status === 'completed' ? '已完成' : '进行中' }}</td></tr>
        </table>
      </ReportSection>

      <ReportSection title="数据概况">
        <div v-if="analysis?.dataOverview">
          <p>共分析数据 <strong>{{ (analysis.dataOverview as {rows:number}).rows }}</strong> 行，
          <strong>{{ (analysis.dataOverview as {cols:number}).cols }}</strong> 列。</p>
        </div>
        <p v-else class="no-data">尚未完成数据分析</p>
      </ReportSection>

      <ReportSection title="异常检测结果">
        <div v-if="analysis?.anomalyCount !== undefined">
          <p :class="{ 'text-danger': (analysis.anomalyCount as number) > 0 }">
            检测到 <strong>{{ analysis.anomalyCount }}</strong> 条异常记录。
          </p>
        </div>
        <p v-else class="no-data">尚未完成异常检测</p>
      </ReportSection>

      <ReportSection title="风险评估结论">
        <div v-if="risk">
          <p>
            风险评分：<strong :class="{
              'text-danger': risk.riskLevel === 'high',
              'text-warning': risk.riskLevel === 'medium',
              'text-success': risk.riskLevel === 'low',
            }">{{ risk.riskScore }}</strong> 分
          </p>
          <p>
            风险等级：<strong :class="{
              'text-danger': risk.riskLevel === 'high',
              'text-warning': risk.riskLevel === 'medium',
              'text-success': risk.riskLevel === 'low',
            }">{{ riskLevelText }}</strong>
          </p>
        </div>
        <p v-else class="no-data">尚未完成风险评估</p>
      </ReportSection>
    </div>

    <div class="report-actions">
      <el-button size="large" @click="handlePrint">打印报告</el-button>
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
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 24px;
}
.report-document {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 40px 48px;
  max-width: 800px;
  margin: 0 auto;
}
.report-header-block {
  text-align: center;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--app-text);
}
.report-doc-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--app-text);
  margin: 0;
}
.info-table {
  width: 100%;
  border-collapse: collapse;
}
.info-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--app-border);
  font-size: 15px;
}
.info-label {
  width: 120px;
  color: var(--app-text-secondary);
  font-weight: 500;
}
.no-data {
  color: var(--app-text-secondary);
  font-style: italic;
}
.text-danger { color: var(--app-danger); }
.text-warning { color: var(--app-warning); }
.text-success { color: var(--app-success); }
.report-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 32px;
  padding-bottom: 24px;
}

@media print {
  .report-actions { display: none; }
  .report-page :deep(.step-indicator) { display: none; }
  .page-subtitle { display: none; }
}
</style>
