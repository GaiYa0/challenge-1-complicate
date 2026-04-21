<script setup lang="ts">
defineProps<{
  name: string
  caseNumber?: string | null
  status: string
  createdAt: string
  fileCount?: number
}>()

defineEmits<{
  click: []
  delete: []
  rename: []
}>()
</script>

<template>
  <div class="case-card" @click="$emit('click')">
    <div class="case-card-header">
      <h3 class="case-card-title">{{ name }}</h3>
      <div class="header-badges">
        <span
          class="case-card-badge"
          :class="status === 'completed' ? 'badge-done' : 'badge-active'"
        >
          {{ status === 'completed' ? '已完成' : '进行中' }}
        </span>
      </div>
    </div>
    <div class="case-card-meta">
      <span v-if="caseNumber" class="meta-item">编号：{{ caseNumber }}</span>
      <span class="meta-item">创建：{{ createdAt.slice(0, 10) }}</span>
      <span v-if="fileCount !== undefined" class="meta-item">{{ fileCount }} 个数据文件</span>
    </div>
    <div class="case-card-footer">
      <div class="footer-actions">
        <span class="case-card-action action-rename" @click.stop="$emit('rename')">重命名</span>
        <span class="case-card-action action-delete" @click.stop="$emit('delete')">删除</span>
      </div>
      <span class="case-card-enter">进入案件 &rarr;</span>
    </div>
  </div>
</template>

<style scoped>
.case-card {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 20px 24px;
  cursor: pointer;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.case-card:hover {
  box-shadow: var(--app-shadow-hover);
  border-color: var(--app-primary);
}
.case-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.case-card-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--app-text);
}
.case-card-badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 500;
}
.badge-active {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge-done {
  background: #dcfce7;
  color: #15803d;
}
.case-card-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.meta-item {
  font-size: 13px;
  color: var(--app-text-secondary);
}
.header-badges {
  display: flex;
  gap: 6px;
  align-items: center;
}

.case-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.footer-actions {
  display: flex;
  gap: 14px;
}
.case-card-action {
  font-size: 13px;
  cursor: pointer;
}
.action-rename {
  color: var(--app-primary);
}
.action-delete {
  color: var(--app-danger);
}
.case-card-action:hover {
  text-decoration: underline;
}
.case-card-enter {
  font-size: 13px;
  color: var(--app-primary);
  font-weight: 500;
}
</style>
