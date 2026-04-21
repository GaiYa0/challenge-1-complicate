<script setup lang="ts">
/**
 * 多维可视化 — 资金流向有向图：边宽∝金额，箭头表示方向；可传入路径高亮
 * 数据：GET /analysis/fund
 */
import echarts, { type ECharts, type EChartsOption } from '../../utils/echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getAnalysisFundViz, type FundVizData } from '../../api/analysisViz'
import {
  buildFundFlowGraphOption,
  highlightPathEdgeIds,
} from '../../utils/analysisVizTransform'
import { useEchartsTheme } from '../../composables/useEchartsTheme'

const props = withDefaults(
  defineProps<{
    dataOverride?: FundVizData | null
    /** 按节点 id 顺序的路径，用于高亮链路上的边 */
    highlightPath?: string[]
    edgeLimit?: number
  }>(),
  { dataOverride: null, highlightPath: () => [], edgeLimit: 500 },
)

const emit = defineEmits<{
  nodeClick: [nodeId: string]
  edgeClick: [source: string, target: string, value: number]
}>()

const loading = ref(false)
const err = ref<string | null>(null)
const raw = ref<FundVizData | null>(null)
const hostRef = ref<HTMLDivElement | null>(null)
const { themeName, onThemeChange } = useEchartsTheme()
let chart: ECharts | null = null

function resize() {
  chart?.resize()
}

function mount() {
  const el = hostRef.value
  if (!el || chart) return
  chart = echarts.init(el, themeName.value)
  chart.on('click', (p) => {
    if (p.dataType === 'node' && p.data && typeof (p.data as { id?: string }).id === 'string') {
      emit('nodeClick', (p.data as { id: string }).id)
    }
    if (p.dataType === 'edge' && p.data) {
      const d = p.data as { source?: string; target?: string; value?: number }
      if (d.source && d.target) {
        emit('edgeClick', d.source, d.target, Number(d.value ?? 0))
      }
    }
  })
  applyOption()
}

function applyOption() {
  if (!chart || !raw.value) return
  const hl =
    props.highlightPath?.length && props.highlightPath.length >= 2
      ? highlightPathEdgeIds(raw.value.graph_edges, props.highlightPath)
      : undefined
  const opt = buildFundFlowGraphOption(
    raw.value.graph_nodes,
    raw.value.graph_edges,
    hl,
  ) as EChartsOption
  chart.setOption(opt, { notMerge: true })
}

async function load() {
  if (props.dataOverride) {
    raw.value = props.dataOverride
    void nextTick(() => applyOption())
    return
  }
  loading.value = true
  err.value = null
  try {
    raw.value = await getAnalysisFundViz(props.edgeLimit)
    void nextTick(() => applyOption())
  } catch (e) {
    err.value = String((e as Error)?.message ?? e)
    raw.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void nextTick(() => {
    mount()
    window.addEventListener('resize', resize)
    void load()
  })
})

onThemeChange(() => {
  try { chart?.dispose() } catch { /* noop */ }
  chart = null
  void nextTick(() => {
    mount()
    applyOption()
  })
})

watch(
  () => props.dataOverride,
  (v) => {
    if (v) {
      raw.value = v
      void nextTick(() => applyOption())
    }
  },
)

watch(
  () => [props.highlightPath, raw.value] as const,
  () => {
    void nextTick(() => applyOption())
  },
  { deep: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="viz-wrap">
    <div class="viz-toolbar">
      <el-button size="small" type="primary" plain :loading="loading" @click="load">刷新数据</el-button>
      <span class="viz-hint">拖拽平移缩放；点击节点/边可在外层联动。路径高亮请传 highlightPath</span>
    </div>
    <p v-if="err" class="viz-err">{{ err }}</p>
    <div v-show="!err" ref="hostRef" class="viz-chart-host" />
  </div>
</template>

<style scoped>
.viz-wrap {
  width: 100%;
}
.viz-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.viz-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.viz-err {
  color: var(--el-color-danger);
  padding: 12px;
}
.viz-chart-host {
  width: 100%;
  height: 460px;
  min-height: 360px;
}
</style>
