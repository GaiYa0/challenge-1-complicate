<script setup lang="ts">
/**
 * 证据筛选面板 — 按类型 / 时间 / 关联人筛选
 */
import type { ActionType } from '../../types/evidence'
import { ACTION_TYPE_LABELS } from '../../types/evidence'

const props = defineProps<{
  activeType: ActionType | 'all'
  personList: { id: string; name: string }[]
  selectedPersonId: string | null
}>()

const emit = defineEmits<{
  (e: 'update:activeType', val: ActionType | 'all'): void
  (e: 'update:selectedPersonId', val: string | null): void
  (e: 'reset'): void
}>()

const typeOptions: { value: ActionType | 'all'; label: string }[] = [
  { value: 'all', label: '全部类型' },
  { value: 'fund', label: ACTION_TYPE_LABELS.fund },
  { value: 'call', label: ACTION_TYPE_LABELS.call },
  { value: 'trip', label: ACTION_TYPE_LABELS.trip },
  { value: 'other', label: ACTION_TYPE_LABELS.other },
]
</script>

<template>
  <div class="ev-filter-panel">
    <div class="filter-group">
      <span class="filter-title">证据类型</span>
      <div class="filter-chips">
        <button
          v-for="opt in typeOptions"
          :key="opt.value"
          :class="['chip', { active: props.activeType === opt.value }]"
          @click="emit('update:activeType', opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
    <div class="filter-group" v-if="personList.length > 0">
      <span class="filter-title">关联人</span>
      <div class="filter-chips">
        <button
          :class="['chip', { active: props.selectedPersonId === null }]"
          @click="emit('update:selectedPersonId', null)"
        >
          全部
        </button>
        <button
          v-for="p in personList"
          :key="p.id"
          :class="['chip', { active: props.selectedPersonId === p.id }]"
          @click="emit('update:selectedPersonId', p.id)"
        >
          {{ p.name }}
        </button>
      </div>
    </div>
    <el-button text size="small" @click="emit('reset')">重置筛选</el-button>
  </div>
</template>

<style scoped>
.ev-filter-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
  padding: 12px 16px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  margin-bottom: 12px;
}
.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  white-space: nowrap;
}
.filter-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chip {
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid var(--app-border);
  background: transparent;
  font-size: 12px;
  color: var(--app-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.chip:hover {
  border-color: var(--app-primary);
  color: var(--app-primary);
}
.chip.active {
  background: var(--app-primary);
  border-color: var(--app-primary);
  color: #fff;
  font-weight: 600;
}
</style>
