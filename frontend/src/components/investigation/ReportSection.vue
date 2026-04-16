<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<template>
  <section class="report-section">
    <h2 class="report-section-title">{{ title }}</h2>
    <div class="report-section-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.report-section {
  margin-bottom: 32px;
}
.report-section-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--app-primary);
}
.report-section-body {
  font-size: 15px;
  line-height: 1.8;
  color: var(--app-text);
}
</style>
