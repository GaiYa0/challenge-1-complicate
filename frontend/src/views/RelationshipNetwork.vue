<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { NodeData } from '@antv/g6'
import { useCaseStore } from '../store/case'
import { useRelationshipAnalysisStore } from '../store/relationshipAnalysis'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import StatCard from '../components/investigation/StatCard.vue'
import GraphView from '../components/graph/GraphView.vue'
import ClueGraph from '../components/graph/ClueGraph.vue'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const rel = useRelationshipAnalysisStore()

const caseId = computed(() => Number(route.params.caseId))

const nodeCount = computed(() => rel.graphData?.nodes.length ?? 0)
const edgeCount = computed(() => rel.graphData?.edges.length ?? 0)
const topTransferor = computed(() => {
  if (rel.degreeList.length === 0) return '—'
  return rel.degreeList[0].name
})

watch(
  caseId,
  (id) => {
    if (!Number.isFinite(id) || id <= 0) return
    caseStore.selectCase(id)
    rel.bindCase(id)
    void rel.loadMainGraph()
  },
  { immediate: true },
)

function goNext() {
  router.push(`/cases/${caseId.value}/risk`)
}

function onGraphNodeClick(payload: { id: string; data: NodeData }) {
  if (rel.mode !== 'main') return
  const raw = payload.data?.data as { label?: string } | undefined
  const label =
    raw?.label != null
      ? String(raw.label)
      : rel.graphData?.nodes.find((n) => n.id === payload.id)?.label ?? payload.id
  void rel.enterClueView(payload.id, String(label))
}
</script>

<template>
  <div class="network-page">
    <StepIndicator :current="3" />

    <h1 class="page-title">关系网络</h1>
    <p class="page-subtitle">展示涉案人员之间的资金往来关系</p>

    <div v-if="rel.mainLoading && !rel.graphData" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="rel.graphError" class="error-state">
      <el-result icon="error" title="关系图加载失败" :sub-title="rel.graphError">
        <template #extra>
          <el-button type="primary" @click="rel.loadMainGraph()">重试</el-button>
        </template>
      </el-result>
    </div>

    <template v-else-if="rel.graphData && rel.hasGraphNodes">
      <div class="stats-row">
        <StatCard label="涉及人员" :value="`${nodeCount} 人`" icon="&#128101;" />
        <StatCard label="资金往来" :value="`${edgeCount} 笔`" icon="&#128176;" />
        <StatCard label="最大转出" :value="topTransferor" icon="&#128200;" />
      </div>

      <div class="graph-container" v-loading="rel.mainLoading">
        <p v-if="rel.mode === 'main'" class="graph-action-hint">点击人物节点进入同心圆线索分析视图</p>
        <GraphView
          v-if="rel.mode === 'main'"
          variant="neo4j"
          :neo4j-data="rel.graphData"
          :show-heading="false"
          :loading="false"
          @node-click="onGraphNodeClick"
        />
        <ClueGraph
          v-else-if="rel.selectedPersonId"
          :person-id="rel.selectedPersonId"
          :person-label="rel.selectedPersonLabel"
          :clues="rel.personClues"
          :loading="rel.cluesLoading"
          @back="rel.exitClueView()"
        />
      </div>

      <div v-if="rel.degreeList.length > 0" class="degree-section">
        <h3 class="section-title">高频转账人员</h3>
        <el-table :data="rel.degreeList.slice(0, 10)" size="small" stripe>
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
.graph-action-hint {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0 0 12px;
}
.section-title {
  font-size: 16px; font-weight: 600; margin: 0 0 12px; color: var(--app-text);
}
.degree-section { margin-bottom: 24px; }
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 16px; }
.loading-state { padding: 40px 0; }
.error-state { padding: 32px 0; }
.page-footer { text-align: center; margin-top: 24px; padding-bottom: 20px; }
</style>
