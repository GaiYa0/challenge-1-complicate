<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { useClueStore } from '../store/modules/clue.store'
import { notifyError } from '../utils/notify'
import StatusTag from '../components/common/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const clueStore = useClueStore()

const { currentDetail: clue, detailLoading: loading, detailError } = storeToRefs(clueStore)

const caseId = computed(() => Number(route.params.caseId))
const clueId = computed(() => Number(route.params.clueId))

async function load() {
  if (!Number.isFinite(clueId.value)) return
  const data = await clueStore.fetchDetail(clueId.value, { force: true })
  if (data === null && detailError.value) {
    notifyError(detailError.value || '加载线索失败')
  }
}

function back() {
  if (clue.value?.person_id) {
    void router.push({
      name: 'PersonPortrait',
      params: {
        caseId: String(caseId.value),
        personId: encodeURIComponent(clue.value.person_id),
      },
    })
    return
  }
  void router.push({ name: 'CaseList' })
}

onMounted(() => {
  if (Number.isFinite(caseId.value)) caseStore.selectCase(caseId.value)
  void load()
})
</script>

<template>
  <div class="clue-detail">
    <el-page-header @back="back">
      <template #content>
        <span class="title">线索详情</span>
      </template>
    </el-page-header>

    <el-skeleton v-if="loading" :rows="8" animated />

    <el-card v-else-if="clue" class="card" shadow="never">
      <h2 class="headline">{{ clue.title }}</h2>
      <el-descriptions :column="2" border size="small" class="meta">
        <el-descriptions-item label="线索编号">{{ clue.id }}</el-descriptions-item>
        <el-descriptions-item label="关联案件">{{ clue.case_id }}</el-descriptions-item>
        <el-descriptions-item label="关联人物">{{ clue.person_id }}</el-descriptions-item>
        <el-descriptions-item label="线索类别">{{ clue.category }}</el-descriptions-item>
        <el-descriptions-item label="风险等级">
          <StatusTag :raw="clue.risk_level" size="small" />
        </el-descriptions-item>
        <el-descriptions-item label="风险评分">{{ clue.risk_score?.toFixed(0) ?? '—' }} / 100</el-descriptions-item>
      </el-descriptions>

      <section v-if="clue.summary" class="block">
        <h3>摘要</h3>
        <p>{{ clue.summary }}</p>
      </section>

      <section class="block evidence-block">
        <h3>来源规则</h3>
        <p>{{ clue.category || '系统自动检测规则' }}</p>
      </section>

      <section class="block evidence-block">
        <h3>命中条件</h3>
        <p v-if="clue.risk_score >= 70">
          风险评分超过高风险阈值（70分），且属于「{{ clue.category || '综合' }}」类型线索。
          <template v-if="clue.rule_hits?.length">触发了 {{ clue.rule_hits.length }} 条规则。</template>
        </p>
        <p v-else-if="clue.risk_score >= 30">
          风险评分达到中风险区间（30-70分），需人工复核。
        </p>
        <p v-else>
          风险评分低于基准线，仅作信息记录。
        </p>
      </section>

      <section class="block evidence-block">
        <h3>数据依据</h3>
        <p>基于清洗后数据分析得出，案件编号 {{ clue.case_id }}，检测对象「{{ clue.person_id }}」关联的异常模式匹配。</p>
        <div v-if="clue.feature_snapshot && Object.keys(clue.feature_snapshot).length > 0" class="feature-snapshot">
          <h4>特征快照</h4>
          <pre class="json">{{ JSON.stringify(clue.feature_snapshot, null, 2) }}</pre>
        </div>
      </section>

      <section v-if="clue.rule_hits?.length" class="block">
        <h3>规则命中明细</h3>
        <pre class="json">{{ JSON.stringify(clue.rule_hits, null, 2) }}</pre>
      </section>
    </el-card>

    <el-empty v-else description="未找到线索" />
  </div>
</template>

<style scoped>
.clue-detail {
  max-width: 900px;
  margin: 0 auto;
}
.title {
  font-weight: 600;
}
.card {
  margin-top: 16px;
  border-radius: 8px;
}
.headline {
  margin: 0 0 12px;
  font-size: 18px;
}
.meta {
  margin-bottom: 16px;
}
.block h3 {
  font-size: 14px;
  margin: 12px 0 8px;
  font-weight: 600;
  color: var(--app-text);
}
.block h4 {
  font-size: 13px;
  margin: 8px 0 6px;
  color: var(--app-text-secondary);
}
.block p {
  margin: 0;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
.evidence-block {
  background: var(--app-bg-layout);
  border-radius: var(--app-radius);
  padding: 12px 16px;
  margin-top: 12px;
}
.json {
  font-size: 12px;
  overflow: auto;
  background: var(--el-fill-color-light);
  padding: 8px;
  border-radius: 4px;
}
</style>
