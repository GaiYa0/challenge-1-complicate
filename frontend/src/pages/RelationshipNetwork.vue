<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCaseStore } from '../store/case'
import { getAnalysisGraph } from '../api/graph'
import { listGraphOutDegree } from '../api/graph'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import StatCard from '../components/investigation/StatCard.vue'
import GraphView from '../components/graph/GraphView.vue'
import type { Neo4jGraphPayload } from '../components/graph/GraphView.vue'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const caseId = computed(() => Number(route.params.caseId))

const graphData = ref<Neo4jGraphPayload | null>(null)
const degreeList = ref<{ name: string; degree: number }[]>([])
const loading = ref(true)

const nodeCount = computed(() => graphData.value?.nodes.length ?? 0)
const edgeCount = computed(() => graphData.value?.edges.length ?? 0)
const topTransferor = computed(() => {
  if (degreeList.value.length === 0) return '—'
  return degreeList.value[0].name
})

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  loading.value = true
  try {
    const [graphRes, degreeRes] = await Promise.allSettled([
      getAnalysisGraph(500),
      listGraphOutDegree(),
    ])
    if (graphRes.status === 'fulfilled') {
      graphData.value = graphRes.value as unknown as Neo4jGraphPayload
    }
    if (degreeRes.status === 'fulfilled') {
      const raw = degreeRes.value as unknown as { name: string; degree: number }[]
      degreeList.value = raw.sort((a, b) => b.degree - a.degree)
    }
  } finally {
    loading.value = false
  }
})

function goNext() {
  router.push(`/cases/${caseId.value}/risk`)
}
</script>

<template>
  <div class="network-page">
    <StepIndicator :current="3" />

    <h1 class="page-title">关系网络</h1>
    <p class="page-subtitle">展示涉案人员之间的资金往来关系</p>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <template v-else-if="graphData && graphData.nodes.length > 0">
      <div class="stats-row">
        <StatCard label="涉及人员" :value="`${nodeCount} 人`" icon="&#128101;" />
        <StatCard label="资金往来" :value="`${edgeCount} 笔`" icon="&#128176;" />
        <StatCard label="最大转出" :value="topTransferor" icon="&#128200;" />
      </div>

      <div class="graph-container">
        <GraphView variant="neo4j" :neo4j-data="graphData" :show-heading="false" :loading="false" />
      </div>

      <div v-if="degreeList.length > 0" class="degree-section">
        <h3 class="section-title">高频转账人员</h3>
        <el-table :data="degreeList.slice(0, 10)" size="small" stripe>
          <el-table-column prop="name" label="姓名" />
          <el-table-column prop="degree" label="转出次数" width="120" align="center" />
        </el-table>
      </div>
    </template>

    <div v-else class="empty-state">
      <p>暂无关系数据，请先完成数据分析</p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/analyze`)">
        去分析数据
      </el-button>
    </div>

    <div class="page-footer">
      <el-button type="primary" size="large" @click="goNext">下一步：查看风险画像 &rarr;</el-button>
    </div>
  </div>
</template>

<style scoped>
.network-page { max-width: 1000px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 24px;
}
.stats-row {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16px; margin-bottom: 24px;
}
.graph-container {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 16px;
  margin-bottom: 24px;
  min-height: 500px;
}
.section-title {
  font-size: 16px; font-weight: 600; margin: 0 0 12px; color: var(--app-text);
}
.degree-section { margin-bottom: 24px; }
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 16px; }
.loading-state { padding: 40px 0; }
.page-footer { text-align: center; margin-top: 24px; padding-bottom: 20px; }
</style>
