<script setup lang="ts">
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { throttle } from '../../utils/throttle'

const props = defineProps<{
  option: EChartsOption
}>()

const hostRef = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null

function resize() {
  chart?.resize()
}

/** 高频 option 变更时用节流 + lazyUpdate，减少布局与绘制次数 */
const applyOptionThrottled = throttle((opt: EChartsOption) => {
  if (!chart) return
  chart.setOption(opt, {
    lazyUpdate: true,
    notMerge: false,
    replaceMerge: ['series', 'dataset'],
  })
}, 80)

onMounted(() => {
  void nextTick(() => {
    const el = hostRef.value
    if (!el) return
    chart = echarts.init(el)
    chart.setOption(props.option, { lazyUpdate: false, notMerge: true })
    window.addEventListener('resize', resize)
  })
})

watch(
  () => props.option,
  (opt) => {
    if (!chart) return
    applyOptionThrottled(opt)
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
  <div ref="hostRef" class="base-chart-host" />
</template>

<style scoped>
.base-chart-host {
  width: 100%;
  height: 280px;
  min-height: 200px;
}
</style>
