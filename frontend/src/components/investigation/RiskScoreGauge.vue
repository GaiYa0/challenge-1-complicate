<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
  level: 'low' | 'medium' | 'high'
}>()

const color = computed(() => {
  if (props.level === 'high') return 'var(--app-danger, #dc2626)'
  if (props.level === 'medium') return 'var(--app-warning, #d97706)'
  return 'var(--app-success, #16a34a)'
})

const levelText = computed(() => {
  if (props.level === 'high') return '高风险'
  if (props.level === 'medium') return '中等风险'
  return '低风险'
})

const dashOffset = computed(() => {
  const circumference = 2 * Math.PI * 54
  return circumference - (props.score / 100) * circumference
})
</script>

<template>
  <div class="risk-gauge">
    <svg viewBox="0 0 120 120" class="gauge-svg">
      <circle cx="60" cy="60" r="54" fill="none" stroke="#e5e7eb" stroke-width="8" />
      <circle
        cx="60" cy="60" r="54" fill="none"
        :stroke="color"
        stroke-width="8"
        stroke-linecap="round"
        :stroke-dasharray="2 * Math.PI * 54"
        :stroke-dashoffset="dashOffset"
        transform="rotate(-90 60 60)"
        class="gauge-arc"
      />
    </svg>
    <div class="gauge-center">
      <span class="gauge-score" :style="{ color }">{{ score }}</span>
      <span class="gauge-label">风险评分</span>
    </div>
    <div class="gauge-level" :style="{ color }">{{ levelText }}</div>
  </div>
</template>

<style scoped>
.risk-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}
.gauge-svg {
  width: 180px;
  height: 180px;
}
.gauge-arc {
  transition: stroke-dashoffset 0.8s ease;
}
.gauge-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -60%);
  text-align: center;
}
.gauge-score {
  font-size: 42px;
  font-weight: 700;
  line-height: 1;
}
.gauge-label {
  display: block;
  font-size: 12px;
  color: var(--app-text-secondary);
  margin-top: 4px;
}
.gauge-level {
  font-size: 18px;
  font-weight: 600;
  margin-top: 8px;
}
</style>
