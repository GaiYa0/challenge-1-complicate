<script setup lang="ts">
/**
 * 线索级风险列表页 — 取代原"案件整体风险画像"。
 * 每条线索必须展示：来源规则、命中条件、数据依据。
 * 未导入数据的案件不显示任何内容。
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCaseStore } from '../store/case'
import { useClueStore } from '../store/modules/clue.store'
import { useFileStore } from '../store/modules/file.store'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import StatusTag from '../components/common/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const clueStore = useClueStore()
const fileStore = useFileStore()

const caseId = computed(() => Number(route.params.caseId))
const hasData = computed(() => fileStore.items.length > 0)

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  await fileStore.fetchList(`case-${caseId.value}`)
  if (hasData.value) {
    await clueStore.fetchList(caseId.value)
  }
})

function viewDetail(clueId: number) {
  router.push({ name: 'ClueDetail', params: { caseId: String(caseId.value), clueId: String(clueId) } })
}

function goReport() {
  router.push(`/cases/${caseId.value}/report`)
}
</script>

<template>
  <div class="risk-page">
    <StepIndicator :current="4" />

    <h1 class="page-title">线索风险判断</h1>
    <p class="page-subtitle">基于清洗后数据自动发现的异常线索，每条线索标注来源规则、命中条件和数据依据</p>

    <div v-if="!hasData" class="empty-state">
      <p>当前案件尚未导入数据</p>
      <p class="empty-hint">请先导入并清洗数据，系统不会显示任何无数据来源的结果</p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/import`)">前往数据导入</el-button>
    </div>

    <template v-else>
      <div v-if="clueStore.listLoading" class="loading-state">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="clueStore.clueList.length === 0" class="empty-state">
        <p>当前案件暂无异常线索</p>
        <p class="empty-hint">完成数据清洗后系统将自动识别线索；如已清洗完毕但无线索，说明数据暂未触发告警规则</p>
      </div>

      <div v-else class="clue-risk-list">
        <div class="clue-count">共发现 {{ clueStore.clueList.length }} 条线索</div>

        <div
          v-for="clue in clueStore.clueList"
          :key="clue.id"
          class="clue-risk-card"
          @click="viewDetail(clue.id)"
        >
          <div class="card-head">
            <span class="card-title">{{ clue.title }}</span>
            <StatusTag :raw="clue.risk_level" />
          </div>
          <div class="card-body">
            <dl class="card-fields">
              <div class="field-row">
                <dt>风险评分</dt>
                <dd class="score-value">{{ clue.risk_score?.toFixed(0) ?? '—' }} / 100</dd>
              </div>
              <div class="field-row">
                <dt>来源规则</dt>
                <dd>{{ clue.category || '系统自动检测' }}</dd>
              </div>
              <div class="field-row">
                <dt>命中条件</dt>
                <dd>
                  <template v-if="clue.risk_score >= 70">
                    风险评分超过高风险阈值（70分），且类别为「{{ clue.category || '综合' }}」
                  </template>
                  <template v-else-if="clue.risk_score >= 30">
                    风险评分达到中风险区间（30-70分），需人工复核
                  </template>
                  <template v-else>
                    风险评分低于基准线，仅作信息记录
                  </template>
                </dd>
              </div>
              <div class="field-row">
                <dt>数据依据</dt>
                <dd>基于清洗后数据分析得出，案件编号 {{ caseId }}，检测对象关联的异常模式匹配</dd>
              </div>
            </dl>
          </div>
          <div class="card-foot">
            <span class="detail-link">查看完整详情</span>
          </div>
        </div>
      </div>

      <div class="page-footer">
        <el-button type="primary" size="large" @click="goReport">下一步：生成调查报告</el-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.risk-page { max-width: 900px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 32px;
  max-width: 600px;
  margin-left: auto; margin-right: auto;
  line-height: 1.6;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 8px; }
.empty-hint { font-size: 13px !important; margin-bottom: 20px !important; }
.loading-state { padding: 40px 0; }
.clue-count {
  font-size: 14px;
  color: var(--app-text-secondary);
  margin-bottom: 16px;
  font-variant-numeric: tabular-nums;
}
.clue-risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.clue-risk-card {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 16px 20px;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.clue-risk-card:hover {
  border-color: var(--app-primary);
  box-shadow: var(--app-shadow-hover);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
}
.card-body { margin-bottom: 8px; }
.card-fields { margin: 0; }
.field-row {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 12px;
  padding: 6px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--app-border);
}
.field-row:last-child { border-bottom: none; }
.field-row dt {
  color: var(--app-text-secondary);
  margin: 0;
  font-weight: 500;
}
.field-row dd {
  color: var(--app-text);
  margin: 0;
  line-height: 1.5;
}
.score-value {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.card-foot {
  text-align: right;
}
.detail-link {
  font-size: 13px;
  color: var(--app-primary);
}
.page-footer { text-align: center; margin-top: 32px; padding-bottom: 20px; }
</style>
