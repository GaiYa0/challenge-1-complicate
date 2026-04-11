<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import BarChart from '../components/charts/BarChart.vue'
import LineChart from '../components/charts/LineChart.vue'
import PieChart from '../components/charts/PieChart.vue'
import GraphView from '../components/graph/GraphView.vue'
import VirtualTable from '../components/table/VirtualTable.vue'
import Permission from '../components/Permission.vue'
import { getAnalysisGraph, type GraphVisualizationData } from '../api/graph'
import { useDataStore } from '../store/data'
import { debounce } from '../utils/debounce'
import { notifySuccess } from '../utils/notify'

const dataStore = useDataStore()
const { analysisData, loading, liveScalar } = storeToRefs(dataStore)

const dateRange = ref('2026-04-01 ~ 2026-04-11')
const stressMode = ref(false)
const graphTab = ref<'neo4j' | 'demo'>('neo4j')
const neo4jGraph = ref<GraphVisualizationData | null>(null)
const neo4jGraphLoading = ref(false)
const tableKeyword = ref('')
const tableKeywordDebounced = ref('')
const syncTableKeyword = debounce((v: string) => {
  tableKeywordDebounced.value = v
}, 350)
watch(tableKeyword, (v) => syncTableKeyword(v))

type TableRow = { id: number; name: string; metric: number; status: string }

const tableRows = computed<TableRow[]>(() => analysisData.value?.table ?? [])

const displayRows = computed<TableRow[]>(() => {
  let rows: TableRow[]
  if (!stressMode.value) {
    rows = tableRows.value
  } else {
    const base = tableRows.value
    const extra: TableRow[] = []
    for (let i = 0; i < 5000; i++) {
      extra.push({
        id: 10_000 + i,
        name: `批量行 ${i}`,
        metric: i % 997,
        status: i % 3 === 0 ? '完成' : i % 3 === 1 ? '运行中' : '排队',
      })
    }
    rows = [...base, ...extra]
  }
  const kw = tableKeywordDebounced.value.trim().toLowerCase()
  if (!kw) return rows
  return rows.filter((r) => r.name.toLowerCase().includes(kw))
})

const lineCategories = computed(() => {
  if (!stressMode.value) return analysisData.value?.trend_labels ?? []
  return Array.from({ length: 12_000 }, (_, i) => `T${i}`)
})

const lineValues = computed(() => {
  if (!stressMode.value) return analysisData.value?.trend_values ?? []
  return Array.from({ length: 12_000 }, (_, i) => Math.round(Math.sin(i / 80) * 40 + 100 + (i % 7)))
})

const lineTitle = computed(() =>
  analysisData.value?.headline ? `趋势 · ${analysisData.value.headline}` : '指标趋势',
)
const barTitle = computed(() =>
  analysisData.value?.headline ? `统计 · ${analysisData.value.headline}` : '区域统计',
)
const pieTitle = computed(() =>
  analysisData.value?.headline ? `占比 · ${analysisData.value.headline}` : '来源占比',
)

const lineChartEmpty = computed(
  () => !loading.value && !stressMode.value && lineCategories.value.length === 0,
)
const barChartEmpty = computed(
  () => !loading.value && (analysisData.value?.bar_labels?.length ?? 0) === 0,
)
const pieChartEmpty = computed(() => !loading.value && (analysisData.value?.pie?.length ?? 0) === 0)

const debouncedFilterLog = debounce((v: string) => {
  console.log('[Analysis] 时间筛选（防抖）', v)
}, 400)

watch(dateRange, (v) => debouncedFilterLog(v))

async function loadNeo4jGraph() {
  neo4jGraphLoading.value = true
  try {
    neo4jGraph.value = await getAnalysisGraph(stressMode.value ? 800 : 500)
  } catch {
    neo4jGraph.value = { nodes: [], edges: [] }
  } finally {
    neo4jGraphLoading.value = false
  }
}

async function handleQuery() {
  try {
    await dataStore.fetchAnalysisData()
    notifySuccess('查询完成，数据已刷新')
  } catch {
    /* 失败由 axios 拦截器统一 message，避免静默 */
  } finally {
    await loadNeo4jGraph()
  }
}

onMounted(() => {
  void handleQuery()
})

onBeforeUnmount(() => {
  syncTableKeyword.cancel()
  debouncedFilterLog.cancel()
})
</script>

<template>
  <div class="analysis-page">
    <div class="page-intro">
      <h1 class="page-title">数据分析中心</h1>
      <p class="page-desc">统一筛选、卡片化图表与虚拟列表，适合企业内运营/研发看数场景。</p>
      <p v-if="liveScalar != null" class="live-strip">
        <el-tag type="warning" effect="dark" size="small">WebSocket 标量</el-tag>
        <span class="live-val">最新 update.value = <strong>{{ liveScalar }}</strong>（每约 4s 推送）</span>
      </p>
    </div>

    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-inner">
        <el-form :inline="true" label-position="top" class="toolbar-form">
          <el-form-item label="时间范围">
            <el-input
              v-model="dateRange"
              placeholder="YYYY-MM-DD ~ YYYY-MM-DD"
              clearable
              style="width: 280px"
            />
          </el-form-item>
          <el-form-item label="表格搜索（防抖）">
            <el-input v-model="tableKeyword" placeholder="按名称过滤" clearable style="width: 200px" />
          </el-form-item>
          <el-form-item label="压力测试">
            <el-switch v-model="stressMode" active-text="开" inactive-text="关" />
          </el-form-item>
        </el-form>
        <div class="toolbar-actions">
          <el-button type="primary" :loading="loading" @click="handleQuery">查询</el-button>
          <el-button :disabled="loading" @click="handleQuery">刷新</el-button>
          <Permission role="admin">
            <el-button type="danger" plain :disabled="loading">导出敏感数据（演示）</el-button>
          </Permission>
        </div>
      </div>
    </el-card>

    <!-- 首屏无数据：骨架屏；有数据：卡片 + 区块 loading -->
    <template v-if="loading && !analysisData">
      <el-row :gutter="16" class="chart-row">
        <el-col :xs="24" :sm="24" :md="8">
          <el-skeleton animated :rows="6" />
        </el-col>
        <el-col :xs="24" :sm="24" :md="8">
          <el-skeleton animated :rows="6" />
        </el-col>
        <el-col :xs="24" :sm="24" :md="8">
          <el-skeleton animated :rows="6" />
        </el-col>
      </el-row>
    </template>

    <el-row v-else :gutter="16" class="chart-row">
      <el-col :xs="24" :sm="24" :md="8">
        <el-card class="chart-card-el" shadow="hover" :header="lineTitle">
          <div v-loading="loading" class="chart-body">
            <el-empty v-if="lineChartEmpty" description="暂无趋势数据" />
            <LineChart
              v-else
              :categories="lineCategories"
              :values="lineValues"
              :progressive="stressMode"
              :max-points="1000"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <el-card class="chart-card-el" shadow="hover" :header="barTitle">
          <div v-loading="loading" class="chart-body">
            <el-empty v-if="barChartEmpty" description="暂无统计数据" />
            <BarChart
              v-else
              :categories="analysisData?.bar_labels ?? []"
              :values="analysisData?.bar_values ?? []"
              :max-points="1000"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <el-card class="chart-card-el" shadow="hover" :header="pieTitle">
          <div v-loading="loading" class="chart-body">
            <el-empty v-if="pieChartEmpty" description="暂无占比数据" />
            <PieChart v-else :data="analysisData?.pie ?? []" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="section-card" shadow="hover">
      <template #header>
        <span class="section-title">数据明细</span>
        <span class="section-sub">虚拟滚动 · 万级行可浏览</span>
      </template>
      <VirtualTable v-if="displayRows.length" :items="displayRows" :viewport-height="400" />
      <el-empty v-if="!loading && displayRows.length === 0" description="暂无数据，请先查询" />
    </el-card>

    <el-card class="section-card graph-card" shadow="hover">
      <template #header>
        <span class="section-title">关系拓扑</span>
        <span class="section-sub">G6 · 可拖拽缩放 · Neo4j 真实子图与内置演示可切换</span>
      </template>
      <el-tabs v-model="graphTab" class="graph-tabs" type="border-card">
        <el-tab-pane label="Neo4j 真实数据" name="neo4j">
          <GraphView
            variant="neo4j"
            :neo4j-data="neo4jGraph"
            :loading="neo4jGraphLoading"
            :show-heading="false"
          />
        </el-tab-pane>
        <el-tab-pane label="内置演示（性能）" name="demo">
          <GraphView
            variant="demo"
            :show-heading="false"
            :total-nodes="stressMode ? 200 : 36"
            :initial-cap="stressMode ? 72 : 36"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.analysis-page {
  max-width: 1280px;
  margin: 0 auto;
}

.page-intro {
  margin-bottom: 20px;
}

.page-title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: var(--app-text);
  letter-spacing: 0.02em;
}

.page-desc {
  margin: 0;
  font-size: 14px;
  color: var(--app-text-secondary);
  line-height: 1.6;
  max-width: 720px;
}

.live-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  font-size: 13px;
  color: var(--app-text-secondary);
}

.live-val strong {
  color: var(--app-primary);
}

.toolbar-card {
  margin-bottom: 20px;
  border-radius: var(--app-radius);
  border-color: var(--app-border);
}

.toolbar-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-form {
  flex: 1;
  min-width: 280px;
}

.toolbar-form :deep(.el-form-item) {
  margin-bottom: 0;
  margin-right: 20px;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
  padding-bottom: 2px;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card-el {
  border-radius: var(--app-radius);
  border-color: var(--app-border);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.chart-card-el:hover {
  box-shadow: var(--app-shadow-hover);
  transform: translateY(-2px);
}

.chart-body {
  min-height: 280px;
  position: relative;
}

.section-card {
  margin-bottom: 20px;
  border-radius: var(--app-radius);
  border-color: var(--app-border);
}

.graph-card :deep(.el-card__body) {
  padding-top: 8px;
}

.graph-tabs {
  margin-top: 4px;
}

.graph-tabs :deep(.el-tabs__content) {
  padding: 12px 0 0;
}

.section-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--app-text);
}

.section-sub {
  margin-left: 10px;
  font-size: 12px;
  color: var(--app-text-secondary);
  font-weight: 400;
}
</style>
