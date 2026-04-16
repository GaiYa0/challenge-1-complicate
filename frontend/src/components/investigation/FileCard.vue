<script setup lang="ts">
defineProps<{
  filename: string
  uploadTime?: string
}>()

defineEmits<{
  preview: []
  remove: []
}>()
</script>

<template>
  <div class="file-card">
    <div class="file-card-icon">&#128196;</div>
    <div class="file-card-info">
      <span class="file-card-name">{{ filename }}</span>
      <span v-if="uploadTime" class="file-card-time">{{ uploadTime }}</span>
    </div>
    <div class="file-card-actions">
      <button class="fc-btn fc-btn-preview" @click.stop="$emit('preview')">查看数据</button>
      <button class="fc-btn fc-btn-remove" @click.stop="$emit('remove')">移除</button>
    </div>
  </div>
</template>

<style scoped>
.file-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 14px 20px;
}
.file-card-icon {
  font-size: 28px;
  flex-shrink: 0;
}
.file-card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.file-card-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--app-text);
}
.file-card-time {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.file-card-actions {
  display: flex;
  gap: 8px;
}
.fc-btn {
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.fc-btn:hover { opacity: 0.85; }
.fc-btn-preview {
  background: var(--app-primary-light);
  color: var(--app-primary);
}
.fc-btn-remove {
  background: #fef2f2;
  color: var(--app-danger);
}
</style>
