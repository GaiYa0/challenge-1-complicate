<script setup lang="ts">
/**
 * 多维可视化 — 轨迹热力：网格聚合热力层 + 轨迹散点 + 时空伴随锚点（经纬度平面）
 * 数据：GET /analysis/trip
 */
import type { EChartsOption } from 'echarts'
import { computed, onMounted, ref, watch } from 'vue'
import { getAnalysisTripViz, type TripVizData } from '../../api/analysisViz'
import BaseChart from '../charts/BaseChart.vue'
import { buildTripHeatmapOption } from '../../utils/analysisVizTransform'

const props = withDefaults(
  defineProps<{
    dataOverride?: TripVizData | null
  }>(),
  { dataOverride: null },
)

const loading = ref(false)
const err = ref<string | null>(null)
const raw = ref<TripVizData | null>(null)

async function load() {
  if (props.dataOverride) {
    raw.value = props.dataOverride
    return
  }
  loading.value = true
  err.value = null
  try {
    raw.value = await getAnalysisTripViz()
  } catch (e) {
    err.value = String((e as Error)?.message ?? e)
    raw.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => void load())

watch(
  () => props.dataOverride,
  (v) => {
    if (v) raw.value = v
  },
)

const option = computed<EChartsOption>(() => {
  const d = raw.value
  if (!d) {
    return { title: { text: '暂无数据', left: 'center', top: 'middle' } }
  }
  return buildTripHeatmapOption(d)
})
</script>

<template>
  <div class="viz-wrap">
    <div class="viz-toolbar">
      <el-button size="small" type="primary" plain :loading="loading" @click="load">刷新</el-button>
      <span class="viz-hint">热力为后端网格聚合；蓝点轨迹、红针为时空伴随；支持框选缩放</span>
    </div>
    <p v-if="err" class="viz-err">{{ err }}</p>
    <BaseChart v-else class="viz-tall" :option="option" />
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
.viz-tall :deep(.base-chart-host) {
  height: 440px;
  min-height: 360px;
}
</style>
