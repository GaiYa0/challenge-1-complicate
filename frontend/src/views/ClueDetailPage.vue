<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { useClueStore } from '../store/modules/clue.store'
import { notifyError } from '../utils/notify'

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
        <el-descriptions-item label="线索 ID">{{ clue.id }}</el-descriptions-item>
        <el-descriptions-item label="案件">{{ clue.case_id }}</el-descriptions-item>
        <el-descriptions-item label="人物">{{ clue.person_id }}</el-descriptions-item>
        <el-descriptions-item label="类别">{{ clue.category }}</el-descriptions-item>
        <el-descriptions-item label="风险等级">{{ clue.risk_level }}</el-descriptions-item>
        <el-descriptions-item label="评分">{{ clue.risk_score }}</el-descriptions-item>
      </el-descriptions>
      <section v-if="clue.summary" class="block">
        <h3>摘要</h3>
        <p>{{ clue.summary }}</p>
      </section>
      <section v-if="clue.rule_hits?.length" class="block">
        <h3>规则命中</h3>
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
}
.block p {
  margin: 0;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
.json {
  font-size: 12px;
  overflow: auto;
  background: var(--el-fill-color-light);
  padding: 8px;
  border-radius: 4px;
}
</style>
