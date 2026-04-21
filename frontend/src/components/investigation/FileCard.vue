<script setup lang="ts">
import FormatTime from '../common/FormatTime.vue'

withDefaults(
  defineProps<{
    filename: string
    uploadTime?: string
    tags?: string[]
  }>(),
  { tags: () => [] },
)

defineEmits<{
  preview: []
  remove: []
}>()
</script>

<template>
  <div class="file-card">
    <div class="file-card-info">
      <span class="file-card-name" :title="filename">{{ filename }}</span>
      <div class="file-card-meta">
        <el-tag v-for="t in tags" :key="t" size="small" effect="plain" type="info">{{ t }}</el-tag>
        <span v-if="uploadTime" class="file-card-time">
          <FormatTime :value="uploadTime" />
        </span>
      </div>
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
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.file-card:hover {
  border-color: var(--app-primary);
  box-shadow: var(--app-shadow-hover);
}
.file-card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.file-card-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--app-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.file-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.file-card-time {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.file-card-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
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
html.dark .fc-btn-remove {
  background: rgba(248, 113, 113, 0.12);
}
</style>
