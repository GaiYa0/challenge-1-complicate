<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '../store/user'

const props = withDefaults(
  defineProps<{
    /** 与 <Permission role="admin"> 用法兼容 */
    role?: string
    /** 允许多角色之一 */
    roles?: string[]
  }>(),
  {},
)

const userStore = useUserStore()

const allowed = computed(() => {
  const r = userStore.userInfo?.role
  if (!r) return false
  if (props.role) return r === props.role
  if (props.roles?.length) return props.roles.includes(r)
  return true
})
</script>

<template>
  <slot v-if="allowed" />
</template>
