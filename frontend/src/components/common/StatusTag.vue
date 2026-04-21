<script setup lang="ts">
/**
 * 统一状态 / 风险等级标签：
 * - 所有展示状态的地方都调用 `<StatusTag :raw="caseInfo.status" />`
 * - 映射逻辑集中在 `utils/format.ts` 的 `resolveStatus`
 */
import { computed } from 'vue'
import { resolveStatus, type StatusTone } from '../../utils/format'

const props = defineProps<{
  /** 原始状态字符串；优先级最高 */
  raw?: string | null
  /** 已由调用方自行 resolve 出 label + tone 时使用 */
  label?: string
  tone?: StatusTone
  size?: 'small' | 'default' | 'large'
  plain?: boolean
  effect?: 'light' | 'dark' | 'plain'
}>()

const resolved = computed(() => {
  if (props.label || props.tone) {
    return { label: props.label ?? '—', tone: props.tone ?? 'default' }
  }
  return resolveStatus(props.raw)
})

const elType = computed(() => {
  const t = resolved.value.tone
  if (t === 'default') return 'info'
  return t
})
</script>

<template>
  <el-tag
    :type="elType"
    :size="size ?? 'small'"
    :effect="effect ?? (plain ? 'plain' : 'light')"
    disable-transitions
  >
    {{ resolved.label }}
  </el-tag>
</template>
