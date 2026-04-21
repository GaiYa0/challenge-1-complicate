<script setup lang="ts">
import echarts, { type ECharts, type EChartsOption } from '../../utils/echarts'
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { throttle } from '../../utils/throttle'
import { useLazyRender } from '../../composables/useLazyRender'
import { useEchartsTheme } from '../../composables/useEchartsTheme'

const props = defineProps<{
  option: EChartsOption
  /** 是否启用进入视口后再挂载，默认启用 */
  lazy?: boolean
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const { visible } = useLazyRender(hostRef, { fallbackVisible: true })
const { themeName, onThemeChange } = useEchartsTheme()
let chart: ECharts | null = null

function resize() {
  chart?.resize()
}

const applyOptionThrottled = throttle((opt: EChartsOption) => {
  if (!chart) return
  chart.setOption(opt, {
    lazyUpdate: true,
    notMerge: false,
    replaceMerge: ['series', 'dataset'],
  })
}, 80)

function mount() {
  const el = hostRef.value
  if (!el || chart) return
  chart = echarts.init(el, themeName.value)
  chart.setOption(props.option, { lazyUpdate: false, notMerge: true })
}

watch(
  () => visible.value || props.lazy === false,
  (v) => {
    if (v) void nextTick(() => mount())
  },
  { immediate: true },
)

watch(
  () => props.option,
  (opt) => {
    if (!chart) return
    applyOptionThrottled(opt)
  },
  { deep: true },
)

onThemeChange(() => {
  try { chart?.dispose() } catch { /* noop */ }
  chart = null
  void nextTick(() => mount())
})

if (typeof window !== 'undefined') window.addEventListener('resize', resize)

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('resize', resize)
  try { chart?.dispose() } catch { /* noop */ }
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
