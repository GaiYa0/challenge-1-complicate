<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed, toRef } from 'vue'
import { useProgressivePairs } from '../../composables/useProgressivePairs'
import { downsamplePaired } from '../../utils/downsample'
import BaseChart from './BaseChart.vue'

const props = withDefaults(
  defineProps<{
    categories: string[]
    values: number[]
    title?: string
    seriesName?: string
    /** 最终进入 ECharts 的最大点数 */
    maxPoints?: number
    /** 超长序列时先分段增长再抽样 */
    progressive?: boolean
  }>(),
  {
    title: '',
    seriesName: '请求量',
    maxPoints: 1000,
    progressive: false,
  },
)

const progressiveRef = toRef(props, 'progressive')

const { labels: progLabels, values: progValues } = useProgressivePairs(
  () => props.categories,
  () => props.values,
  { chunk: 250, enabled: () => progressiveRef.value },
)

const display = computed(() => {
  const L = props.progressive ? progLabels.value : props.categories
  const V = props.progressive ? progValues.value : props.values
  return downsamplePaired(L, V, props.maxPoints)
})

const option = computed<EChartsOption>(() => {
  const { labels, values } = display.value
  const rows: (string | number)[][] =
    labels.length === 0
      ? [
          ['类目', '值'],
          ['—', 0],
        ]
      : [['类目', '值'], ...labels.map((t, i) => [t, values[i] ?? 0])]
  const topPad = props.title ? 48 : 28
  return {
    ...(props.title
      ? { title: { text: props.title, left: 'center', textStyle: { fontSize: 13 } } }
      : {}),
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: topPad, bottom: 32 },
    dataset: { source: rows },
    xAxis: { type: 'category' },
    yAxis: { type: 'value' },
    series: [
      {
        name: props.seriesName,
        type: 'line',
        smooth: true,
        encode: { x: '类目', y: '值' },
      },
    ],
  }
})
</script>

<template>
  <BaseChart :option="option" />
</template>
