<script setup lang="ts">
/**
 * 多维可视化 — 时间轴：交易 / 通话 / 异常事件（ECharts 时间轴 + dataZoom 缩放）
 * 数据：GET /analysis/fund
 */
import type { EChartsOption } from 'echarts'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { getAnalysisFundViz, type FundVizData } from '../../api/analysisViz'
import BaseChart from '../charts/BaseChart.vue'
import { buildTimeLineOption, type TimeLineFilters } from '../../utils/analysisVizTransform'

const props = withDefaults(
  defineProps<{
    /** 传入则不再请求接口 */
    dataOverride?: FundVizData | null
    edgeLimit?: number
  }>(),
  { dataOverride: null, edgeLimit: 500 },
)

const loading = ref(false)
const err = ref<string | null>(null)
const raw = ref<FundVizData | null>(null)

const filters = reactive<TimeLineFilters>({
  fund: true,
  call: true,
  anomaly: true,
})

async function load() {
  if (props.dataOverride) {
    raw.value = props.dataOverride
    return
  }
  loading.value = true
  err.value = null
  try {
    raw.value = await getAnalysisFundViz(props.edgeLimit)
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
    return {
      title: { text: '暂无数据', left: 'center', top: 'middle' },
    }
  }
  return buildTimeLineOption(
    {
      fund_events: d.fund_events,
      call_events: d.call_events,
      anomaly_events: d.anomaly_events,
    },
    filters,
  )
})
</script>

<template>
  <div class="viz-wrap">
    <div class="viz-toolbar">
      <span class="viz-label">筛选：</span>
      <el-checkbox v-model="filters.fund">交易</el-checkbox>
      <el-checkbox v-model="filters.call">通话</el-checkbox>
      <el-checkbox v-model="filters.anomaly">异常</el-checkbox>
      <el-button size="small" type="primary" plain :loading="loading" @click="load">刷新</el-button>
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
  gap: 8px 12px;
  margin-bottom: 8px;
}
.viz-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.viz-err {
  color: var(--el-color-danger);
  padding: 12px;
}
.viz-tall :deep(.base-chart-host) {
  height: 420px;
  min-height: 320px;
}
</style>
