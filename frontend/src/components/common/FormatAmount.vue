<script setup lang="ts">
/**
 * 统一金额渲染：千分位 + 可选的"万/亿"缩略 + 可选动画。
 */
import { computed } from 'vue'
import CountUp from './CountUp.vue'
import { formatAmount } from '../../utils/format'

const props = withDefaults(
  defineProps<{
    value: number | string | null | undefined
    currency?: string
    fractionDigits?: number
    compact?: boolean
    animate?: boolean
  }>(),
  { currency: '¥', fractionDigits: 2, compact: false, animate: false },
)

const numericValue = computed(() => {
  const v = Number(props.value)
  return Number.isFinite(v) ? v : 0
})

const staticText = computed(() =>
  formatAmount(props.value, {
    currency: props.currency,
    fractionDigits: props.fractionDigits,
    compact: props.compact,
  }),
)
</script>

<template>
  <span v-if="animate" class="format-amount">
    <CountUp
      :value="numericValue"
      :prefix="currency"
      :fraction-digits="fractionDigits"
      kind="number"
    />
  </span>
  <span v-else class="format-amount">{{ staticText }}</span>
</template>

<style scoped>
.format-amount {
  font-variant-numeric: tabular-nums;
}
</style>
