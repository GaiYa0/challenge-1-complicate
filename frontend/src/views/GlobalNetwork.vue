<script setup lang="ts">
/**
 * 全局关系网络 — 跨案件串联人物关系。
 * 用户选择多个案件后合并展示。
 */
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { NodeData } from '@antv/g6'
import { useCaseStore } from '../store/case'
import { getMergedCasesGraph } from '../api/graph'
import type { MergedGraphData } from '../api/graph'
import GraphView, { type Neo4jGraphPayload } from '../components/graph/GraphView.vue'
import StatCard from '../components/investigation/StatCard.vue'

const caseStore = useCaseStore()
const loading = ref(false)
const error = ref<string | null>(null)
const mergedData = ref<MergedGraphData | null>(null)
const keyword = ref('')
const corePersonId = ref('')
const selectedCaseIds = ref<number[]>([])

const graphPayload = computed<Neo4jGraphPayload | null>(() => {
  if (!mergedData.value) return null
  const nodes = mergedData.value.nodes.map((n) => ({
    id: String(n.id ?? ''),
    label: String(n.label ?? n.id ?? ''),
  }))
  const edges = mergedData.value.edges.map((e, i) => ({
    id: String(e.id ?? `e${i}`),
    source: String(e.source ?? ''),
    target: String(e.target ?? ''),
  }))
  return { nodes, edges }
})

const nodeCount = computed(() => graphPayload.value?.nodes.length ?? 0)
const edgeCount = computed(() => graphPayload.value?.edges.length ?? 0)

const filteredGraph = computed<Neo4jGraphPayload | null>(() => {
  if (!graphPayload.value) return null
  const kw = keyword.value.trim().toLowerCase()
  const core = corePersonId.value.trim()
  const allNodes = graphPayload.value.nodes
  const allEdges = graphPayload.value.edges

  if (!core && !kw) return graphPayload.value

  let seedIds = new Set<string>()

  if (core) {
    const coreNode = allNodes.find(
      (n) => n.id === core || (n.label ?? '').toLowerCase() === core.toLowerCase(),
    )
    if (coreNode) {
      seedIds.add(coreNode.id)
      for (const e of allEdges) {
        if (e.source === coreNode.id) seedIds.add(e.target)
        if (e.target === coreNode.id) seedIds.add(e.source)
      }
    }
  }

  if (kw) {
    const matched = allNodes.filter((n) =>
      (n.label ?? n.id).toString().toLowerCase().includes(kw),
    )
    if (seedIds.size === 0) {
      seedIds = new Set(matched.map((n) => n.id))
      for (const e of allEdges) {
        if (seedIds.has(e.source) || seedIds.has(e.target)) {
          seedIds.add(e.source)
          seedIds.add(e.target)
        }
      }
    } else {
      for (const n of matched) seedIds.add(n.id)
    }
  }

  const nodes = allNodes.filter((n) => seedIds.has(n.id))
  const edges = allEdges.filter((e) => seedIds.has(e.source) && seedIds.has(e.target))
  return { nodes, edges }
})

async function loadMergedGraph() {
  if (selectedCaseIds.value.length === 0) {
    mergedData.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    mergedData.value = await getMergedCasesGraph(selectedCaseIds.value, 200)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    mergedData.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (caseStore.cases.length === 0) void caseStore.fetchCases()
})

function onNodeClick(payload: { id: string; data: NodeData }) {
  const raw = payload.data?.data as { label?: string } | undefined
  const label = raw?.label ?? payload.id
  corePersonId.value = String(label)
}

function resetFilters() {
  keyword.value = ''
  corePersonId.value = ''
}
</script>

<template>
  <div class="global-network-page">
    <h1 class="page-title">全局关系网络</h1>
    <p class="page-subtitle">选择多个案件合并展示人物关系图谱</p>

    <div class="case-selector">
      <el-select
        v-model="selectedCaseIds"
        multiple
        filterable
        collapse-tags
        collapse-tags-tooltip
        placeholder="选择要合并的案件（最多10个）"
        class="case-select"
        size="default"
        @change="loadMergedGraph"
      >
        <el-option
          v-for="c in caseStore.cases"
          :key="c.id"
          :label="c.name"
          :value="c.id"
        />
      </el-select>
    </div>

    <div v-if="selectedCaseIds.length === 0" class="empty-state">
      <p>请先选择案件以查看合并关系网络</p>
      <p class="empty-hint">选择多个案件后，系统将自动合并人物关系图谱</p>
    </div>

    <div v-else-if="loading && !mergedData" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="error" class="error-state">
      <el-result icon="error" title="关系图加载失败" :sub-title="error">
        <template #extra>
          <el-button type="primary" @click="loadMergedGraph()">重试</el-button>
        </template>
      </el-result>
    </div>

    <template v-else-if="graphPayload && nodeCount > 0">
      <div class="stats-row">
        <StatCard label="总人员数" :value="`${nodeCount} 人`" />
        <StatCard label="关系连接" :value="`${edgeCount} 条`" />
        <StatCard label="合并案件数" :value="`${selectedCaseIds.length} 个`" />
      </div>

      <div class="graph-toolbar">
        <el-input
          v-model="corePersonId"
          placeholder="输入核心人物姓名"
          clearable
          class="toolbar-core"
          size="default"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input
          v-model="keyword"
          placeholder="搜索关联人员"
          clearable
          class="toolbar-filter"
          size="default"
        />
        <el-button text @click="resetFilters">重置</el-button>
      </div>

      <div class="graph-container" v-loading="loading">
        <GraphView
          variant="neo4j"
          :neo4j-data="filteredGraph"
          :show-heading="false"
          :loading="false"
          :max-neo-nodes="300"
          @node-click="onNodeClick"
        />
      </div>
    </template>

    <div v-else-if="selectedCaseIds.length > 0 && !loading" class="empty-state">
      <p>当前案件暂无数据</p>
      <p class="empty-hint">请先在各案件中导入数据并完成清洗，关系网络将自动生成</p>
    </div>
  </div>
</template>

<style scoped>
.global-network-page { max-width: 1100px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 24px;
  line-height: 1.6;
}
.case-selector {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
}
.case-select { width: 500px; }
.stats-row {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16px; margin-bottom: 24px;
}
.graph-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 16px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  flex-wrap: wrap;
}
.toolbar-core { width: 300px; }
.toolbar-filter { width: 220px; }
.graph-container {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 16px;
  margin-bottom: 24px;
  min-height: 500px;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 8px; }
.empty-hint { font-size: 13px !important; margin-bottom: 20px !important; }
.loading-state { padding: 40px 0; }
.error-state { padding: 32px 0; }
</style>
