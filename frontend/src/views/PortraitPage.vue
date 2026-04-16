<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { usePortraitStore } from '../store/modules/portrait.store'
import { notifyError } from '../utils/notify'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import PortraitEconomicPanel from '../components/portrait/PortraitEconomicPanel.vue'
import PortraitBehaviorPanel from '../components/portrait/PortraitBehaviorPanel.vue'
import PortraitSocialPanel from '../components/portrait/PortraitSocialPanel.vue'
import PortraitCluesPanel from '../components/portrait/PortraitCluesPanel.vue'

const route = useRoute()
const caseStore = useCaseStore()
const portraitStore = usePortraitStore()

const { loading, current: portrait, lastError } = storeToRefs(portraitStore)

const caseId = computed(() => Number(route.params.caseId))
const personId = computed(() => decodeURIComponent(String(route.params.personId ?? '')))

async function load(opts?: { force?: boolean }) {
  if (!personId.value || !Number.isFinite(caseId.value)) return
  const result = await portraitStore.load(caseId.value, personId.value, opts)
  if (result === null && lastError.value) {
    notifyError(lastError.value || '加载人物画像失败')
  }
}

onMounted(() => {
  caseStore.selectCase(caseId.value)
  void load()
})
</script>

<template>
  <div class="portrait-page">
    <StepIndicator
      :current="4"
      :steps="['数据导入', '开始分析', '关系网络', '人物画像', '风险画像', '调查报告']"
    />

    <header class="page-head">
      <div>
        <h1 class="page-title">人物画像</h1>
        <p class="page-subtitle">
          案件 {{ caseId }} · 对象 <strong>{{ personId }}</strong>
        </p>
      </div>
      <el-button type="primary" plain :loading="loading" @click="load({ force: true })">刷新</el-button>
    </header>

    <el-skeleton v-if="loading" :rows="10" animated />

    <template v-else-if="portrait">
      <el-alert
        class="summary-alert"
        type="info"
        :closable="false"
        :title="`综合风险 ${portrait.basic_info.risk_score}（${portrait.basic_info.risk_level}）`"
        :description="portrait.basic_info.summary"
        show-icon
      />

      <div class="grid">
        <PortraitEconomicPanel :data="portrait.economic" />
        <PortraitBehaviorPanel :data="portrait.behavior" />
        <PortraitSocialPanel
          :case-id="caseId"
          :graph="portrait.social.graph"
          :center-id="portrait.social.center_id"
          :explain="portrait.social.explain"
        />
        <PortraitCluesPanel :case-id="caseId" :clues="portrait.clues" />
      </div>
    </template>

    <el-empty v-else description="暂无数据" />
  </div>
</template>

<style scoped>
.portrait-page {
  max-width: 1280px;
  margin: 0 auto;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.page-title {
  margin: 0 0 4px;
  font-size: 22px;
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.summary-alert {
  margin-bottom: 16px;
}
.grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
