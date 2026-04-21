<script setup lang="ts">
/**
 * 统一时间渲染：传入 ISO 字符串或 Date，吐出 `2024-03-14 12:30`（可带 tooltip 显示相对时间）。
 */
import { computed } from 'vue'
import { formatDateTime, formatRelative } from '../../utils/format'

const props = withDefaults(
  defineProps<{
    value: string | number | Date | null | undefined
    pattern?: string
    showRelative?: boolean
    fallback?: string
  }>(),
  { pattern: 'YYYY-MM-DD HH:mm', showRelative: true, fallback: '—' },
)

const absolute = computed(() => formatDateTime(props.value, props.pattern))
const relative = computed(() => formatRelative(props.value, props.fallback))
</script>

<template>
  <el-tooltip
    v-if="showRelative && absolute !== fallback"
    :content="relative"
    placement="top"
    :show-after="300"
  >
    <span class="format-time">{{ absolute }}</span>
  </el-tooltip>
  <span v-else class="format-time">{{ absolute }}</span>
</template>

<style scoped>
.format-time {
  font-variant-numeric: tabular-nums;
  color: inherit;
}
</style>
