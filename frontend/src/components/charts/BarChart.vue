<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed } from 'vue'
import { downsamplePaired } from '../../utils/downsample'
import BaseChart from './BaseChart.vue'

const props = withDefaults(
  defineProps<{
    categories: string[]
    values: number[]
    title?: string
    seriesName?: string
    maxPoints?: number
  }>(),
  {
    title: '',
    seriesName: '任务数',
    maxPoints: 1000,
  },
)

const display = computed(() => downsamplePaired(props.categories, props.values, props.maxPoints))

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
        type: 'bar',
        encode: { x: '类目', y: '值' },
        itemStyle: { color: '#5470c6' },
      },
    ],
  }
})
</script>

<template>
  <BaseChart :option="option" />
</template>
