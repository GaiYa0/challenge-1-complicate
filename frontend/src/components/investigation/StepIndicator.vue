<script setup lang="ts">
defineProps<{
  current: number
  steps?: string[]
}>()

const defaultSteps = ['数据导入', '数据清洗', '证据关系图', '证据链分析', '证据报告']
</script>

<template>
  <div class="step-indicator">
    <div
      v-for="(step, idx) in (steps ?? defaultSteps)"
      :key="idx"
      class="step-item"
      :class="{
        'step-active': idx + 1 === current,
        'step-done': idx + 1 < current,
        'step-pending': idx + 1 > current,
      }"
    >
      <div class="step-circle">
        <span v-if="idx + 1 < current">&#10003;</span>
        <span v-else>{{ idx + 1 }}</span>
      </div>
      <span class="step-label">{{ step }}</span>
      <div v-if="idx < (steps ?? defaultSteps).length - 1" class="step-line" />
    </div>
  </div>
</template>

<style scoped>
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 0 28px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.step-label {
  font-size: 14px;
  white-space: nowrap;
}
.step-line {
  width: 40px;
  height: 2px;
  margin: 0 8px;
  flex-shrink: 0;
}
.step-active .step-circle {
  background: var(--app-primary);
  color: #fff;
}
.step-active .step-label {
  color: var(--app-primary);
  font-weight: 600;
}
.step-done .step-circle {
  background: var(--app-success, #16a34a);
  color: #fff;
}
.step-done .step-label {
  color: var(--app-text-secondary);
}
.step-pending .step-circle {
  background: #e5e7eb;
  color: #9ca3af;
}
.step-pending .step-label {
  color: #9ca3af;
}
.step-done .step-line,
.step-active .step-line {
  background: var(--app-primary);
}
.step-pending .step-line {
  background: #e5e7eb;
}
</style>
