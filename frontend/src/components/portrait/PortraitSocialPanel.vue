<script setup lang="ts">
import echarts, { type ECharts, type EChartsOption } from '../../utils/echarts'
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { GraphVisualizationData } from '../../api/graph'
import { graphToFundFlowOption } from '../../utils/portraitCharts'
import { useLazyRender } from '../../composables/useLazyRender'
import { useEchartsTheme } from '../../composables/useEchartsTheme'

const props = defineProps<{
  caseId: number
  graph: GraphVisualizationData
  centerId: string
  explain: string
}>()

const router = useRouter()
const hostRef = ref<HTMLDivElement | null>(null)
const { visible } = useLazyRender(hostRef)
const { themeName, onThemeChange } = useEchartsTheme()
let chart: ECharts | null = null

function resize() {
  chart?.resize()
}

function apply() {
  if (!chart || !props.graph?.nodes?.length) return
  const opt = graphToFundFlowOption(props.graph) as EChartsOption
  chart.setOption(opt, { notMerge: true })
}

function mount() {
  const el = hostRef.value
  if (!el || chart) return
  chart = echarts.init(el, themeName.value)
  chart.on('click', () => goNetwork())
  apply()
}

watch(visible, (v) => {
  if (v) void nextTick(() => mount())
})

watch(
  () => props.graph,
  () => void nextTick(() => apply()),
  { deep: true },
)

onThemeChange(() => {
  try { chart?.dispose() } catch { /* noop */ }
  chart = null
  if (visible.value) void nextTick(() => mount())
})

if (typeof window !== 'undefined') {
  window.addEventListener('resize', resize)
}

function goNetwork() {
  void router.push({ name: 'RelationshipNetwork', params: { caseId: String(props.caseId) } })
}

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('resize', resize)
  try { chart?.dispose() } catch { /* noop */ }
  chart = null
})
</script>

<template>
  <el-card class="panel" shadow="never">
    <template #header>
      <div class="hdr">
        <span class="panel-title">社会关系</span>
        <el-button type="primary" link @click="goNetwork">查看全案关系网</el-button>
      </div>
    </template>
    <p class="explain">{{ explain }} 中心人物：<strong>{{ centerId }}</strong></p>
    <div ref="hostRef" class="chart-host" />
  </el-card>
</template>

<style scoped>
.panel {
  border-radius: 8px;
}
.hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
}
.explain {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0 0 8px;
  line-height: 1.5;
}
.chart-host {
  width: 100%;
  height: 420px;
  min-height: 320px;
}
</style>
