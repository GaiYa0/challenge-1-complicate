<script setup lang="ts">
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { GraphVisualizationData } from '../../api/graph'
import { graphToFundFlowOption } from '../../utils/portraitCharts'

const props = defineProps<{
  caseId: number
  graph: GraphVisualizationData
  centerId: string
  explain: string
}>()

const router = useRouter()
const hostRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function resize() {
  chart?.resize()
}

function apply() {
  if (!chart || !props.graph?.nodes?.length) return
  const opt = graphToFundFlowOption(props.graph) as EChartsOption
  chart.setOption(opt, { notMerge: true })
}

onMounted(() => {
  void nextTick(() => {
    const el = hostRef.value
    if (!el) return
    chart = echarts.init(el)
    window.addEventListener('resize', resize)
    apply()
    chart.on('click', () => {
      goNetwork()
    })
  })
})

watch(
  () => props.graph,
  () => void nextTick(() => apply()),
  { deep: true },
)

function goNetwork() {
  void router.push({ name: 'RelationshipNetwork', params: { caseId: String(props.caseId) } })
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
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
