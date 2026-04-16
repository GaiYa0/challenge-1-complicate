/**
 * 基础权限：基于用户角色字符串（与后端 JWT / userInfo.role 对齐）。
 * 路由级权限仍以 router meta + 守卫为主；本 composable 用于按钮/模块显隐。
 */
import { computed } from 'vue'
import { useUserStore } from '../store/user'

export function usePermission() {
  const userStore = useUserStore()

  const roles = computed(() => {
    const r = userStore.userInfo?.role
    if (r == null || r === '') return [] as string[]
    return [String(r)]
  })

  function hasRole(role: string): boolean {
    return roles.value.includes(role)
  }

  function hasAnyRole(candidates: string[]): boolean {
    return candidates.some((c) => roles.value.includes(c))
  }

  function canAccess(required: string | string[] | undefined): boolean {
    if (required == null) return true
    const list = Array.isArray(required) ? required : [required]
    if (list.length === 0) return true
    return hasAnyRole(list)
  }

  return {
    roles,
    hasRole,
    hasAnyRole,
    canAccess,
  }
}
