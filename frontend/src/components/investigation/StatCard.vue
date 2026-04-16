<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  icon?: string
  danger?: boolean
}>()
</script>

<template>
  <div class="stat-card" :class="{ 'stat-danger': danger }">
    <div v-if="icon" class="stat-icon">{{ icon }}</div>
    <div class="stat-body">
      <span class="stat-value">{{ value }}</span>
      <span class="stat-label">{{ label }}</span>
    </div>
  </div>
</template>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 20px 24px;
}
.stat-danger {
  border-color: var(--app-danger);
  background: #fef2f2;
}
.stat-icon {
  font-size: 32px;
  flex-shrink: 0;
}
.stat-body {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--app-text);
  line-height: 1.2;
}
.stat-danger .stat-value {
  color: var(--app-danger);
}
.stat-label {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin-top: 2px;
}
</style>
