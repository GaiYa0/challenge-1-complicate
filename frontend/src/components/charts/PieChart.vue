<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import type { PieSlice } from '../../api/data'

const props = withDefaults(
  defineProps<{
    data: PieSlice[]
    title?: string
  }>(),
  {
    title: '',
  },
)

const option = computed<EChartsOption>(() => ({
  ...(props.title
    ? { title: { text: props.title, left: 'center', textStyle: { fontSize: 13 } } }
    : {}),
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, left: 'center' },
  series: [
    {
      name: '来源',
      type: 'pie',
      radius: ['36%', '62%'],
      avoidLabelOverlap: true,
      data: props.data.length ? props.data : [{ value: 0, name: '暂无' }],
    },
  ],
}))
</script>

<template>
  <BaseChart :option="option" />
</template>
