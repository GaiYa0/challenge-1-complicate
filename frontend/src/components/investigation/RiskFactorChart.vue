<script setup lang="ts">
/**
 * 风险评分因子分解：横向柱状图。
 * - 自动跟随暗色主题；
 * - 空数据给兜底占位，不抛异常；
 * - 懒渲染（仅当进入视口才 init），避免报告页 / 画像页同屏多图卡顿。
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import echarts, { type ECharts, type EChartsOption } from '../../utils/echarts'
import { useLazyRender } from '../../composables/useLazyRender'
import { useEchartsTheme } from '../../composables/useEchartsTheme'

export interface RiskFactor {
  name: string
  value: number
  tone?: 'danger' | 'warning' | 'success' | 'primary'
}

const props = withDefaults(
  defineProps<{
    factors: RiskFactor[]
    height?: number
    title?: string
  }>(),
  { height: 260, title: '' },
)

const hostRef = ref<HTMLDivElement | null>(null)
const { visible } = useLazyRender(hostRef)
const { themeName, onThemeChange } = useEchartsTheme()
let chart: ECharts | null = null

const TONE_COLOR: Record<string, string> = {
  danger: '#dc2626',
  warning: '#d97706',
  success: '#16a34a',
  primary: '#2563eb',
}

function toneColor(f: RiskFactor): string {
  if (f.tone && TONE_COLOR[f.tone]) return TONE_COLOR[f.tone]
  if (f.value >= 70) return TONE_COLOR.danger
  if (f.value >= 40) return TONE_COLOR.warning
  return TONE_COLOR.success
}

function buildOption(): EChartsOption {
  const sorted = [...props.factors].sort((a, b) => a.value - b.value)
  return {
    grid: { top: 12, right: 24, left: 100, bottom: 12, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (v) => `${Number(v).toFixed(0)} / 100`,
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitNumber: 5,
    },
    yAxis: {
      type: 'category',
      data: sorted.map((f) => f.name),
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: sorted.map((f) => ({
          value: Number(f.value.toFixed(0)),
          itemStyle: { color: toneColor(f), borderRadius: [0, 4, 4, 0] },
        })),
        barWidth: 18,
        label: {
          show: true,
          position: 'right',
          formatter: '{c}',
          fontSize: 12,
        },
      },
    ],
  }
}

function mount() {
  const el = hostRef.value
  if (!el || chart) return
  chart = echarts.init(el, themeName.value)
  chart.setOption(buildOption(), { notMerge: true })
}

function apply() {
  if (!chart) return
  chart.setOption(buildOption(), { notMerge: true })
}

function resize() {
  chart?.resize()
}

watch(visible, (v) => {
  if (v) void nextTick(() => mount())
})

watch(() => props.factors, () => {
  void nextTick(() => apply())
}, { deep: true })

onThemeChange(() => {
  try {
    chart?.dispose()
  } catch { /* noop */ }
  chart = null
  void nextTick(() => mount())
})

if (typeof window !== 'undefined') {
  window.addEventListener('resize', resize)
}

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('resize', resize)
  try { chart?.dispose() } catch { /* noop */ }
  chart = null
})
</script>

<template>
  <div class="risk-factor-chart">
    <p v-if="title" class="chart-title">{{ title }}</p>
    <div ref="hostRef" class="chart-host" :style="{ height: `${height}px` }" />
    <p v-if="factors.length === 0" class="chart-empty">暂无因子数据</p>
  </div>
</template>

<style scoped>
.risk-factor-chart { position: relative; }
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 8px;
}
.chart-host {
  width: 100%;
  min-height: 200px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0;
  pointer-events: none;
}
</style>
