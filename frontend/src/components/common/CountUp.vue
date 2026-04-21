<script setup lang="ts">
/**
 * 数值滚动动画（#18 观感抬一档）。
 * - 使用 requestAnimationFrame，单次时长可控（默认 600ms）；
 * - prefers-reduced-motion 下直接落地到终值，不做动画；
 * - 切换目标值时自动从当前显示值过渡到新值。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { formatAmount, formatNumber } from '../../utils/format'

const props = withDefaults(
  defineProps<{
    value: number
    duration?: number
    fractionDigits?: number
    prefix?: string
    suffix?: string
    /** 'number' 千分位；'amount' 带 ¥ 的金额 */
    kind?: 'number' | 'amount'
  }>(),
  { duration: 600, fractionDigits: 0, prefix: '', suffix: '', kind: 'number' },
)

const displayed = ref<number>(Number.isFinite(props.value) ? props.value : 0)
let rafId = 0
let startTs = 0
let fromValue = 0
let toValue = 0

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined'
    && window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function step(now: number) {
  const elapsed = now - startTs
  const t = Math.min(1, elapsed / Math.max(1, props.duration))
  const v = fromValue + (toValue - fromValue) * easeOut(t)
  displayed.value = v
  if (t < 1) rafId = requestAnimationFrame(step)
}

function animateTo(target: number) {
  if (typeof window === 'undefined' || prefersReducedMotion()) {
    displayed.value = target
    return
  }
  cancelAnimationFrame(rafId)
  fromValue = displayed.value
  toValue = target
  startTs = performance.now()
  rafId = requestAnimationFrame(step)
}

watch(
  () => props.value,
  (v) => {
    animateTo(Number.isFinite(v) ? Number(v) : 0)
  },
  { immediate: false },
)

onBeforeUnmount(() => {
  cancelAnimationFrame(rafId)
})

const formatted = computed(() => {
  const v = displayed.value
  if (props.kind === 'amount') return formatAmount(v, { fractionDigits: props.fractionDigits })
  return formatNumber(v, props.fractionDigits)
})
</script>

<template>
  <span class="count-up">{{ prefix }}{{ formatted }}{{ suffix }}</span>
</template>

<style scoped>
.count-up {
  font-variant-numeric: tabular-nums;
}
</style>
