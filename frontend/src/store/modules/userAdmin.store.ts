/**
 * 用户管理（admin）Store：列表 / 单删 / 批量删除。
 * 与当前登录态 `useUserStore` 解耦。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

import { deleteUser, fetchUsers, type UserListItem } from '../../api/users'

export const useUserAdminStore = defineStore('userAdmin', () => {
  const list = ref<UserListItem[]>([])
  const loading = ref(false)
  const batchLoading = ref(false)
  const rowDeletingId = ref<number | null>(null)
  const lastError = ref<string | null>(null)

  async function fetchList(): Promise<UserListItem[]> {
    loading.value = true
    lastError.value = null
    try {
      const rows = await fetchUsers()
      list.value = Array.isArray(rows) ? rows : []
      return list.value
    } catch (e) {
      list.value = []
      lastError.value = e instanceof Error ? e.message : String(e)
      return []
    } finally {
      loading.value = false
    }
  }

  async function removeById(id: number): Promise<void> {
    rowDeletingId.value = id
    try {
      await deleteUser(id)
      await fetchList()
    } finally {
      rowDeletingId.value = null
    }
  }

  async function removeMany(ids: readonly number[]): Promise<{ success: number; failed: number }> {
    const unique = Array.from(new Set(ids.filter((id) => Number.isFinite(id))))
    if (unique.length === 0) return { success: 0, failed: 0 }
    batchLoading.value = true
    let success = 0
    let failed = 0
    try {
      for (const id of unique) {
        try {
          await deleteUser(id)
          success += 1
        } catch (e) {
          failed += 1
          console.warn('[userAdmin.store] delete failed', id, e)
        }
      }
      await fetchList()
      return { success, failed }
    } finally {
      batchLoading.value = false
    }
  }

  function deletableIds(excludeId: number | null | undefined): number[] {
    const exclude = Number(excludeId ?? NaN)
    return list.value
      .map((u) => u.id)
      .filter((id) => Number.isFinite(id) && id !== exclude)
  }

  function reset() {
    list.value = []
    loading.value = false
    batchLoading.value = false
    rowDeletingId.value = null
    lastError.value = null
  }

  return {
    list,
    loading,
    batchLoading,
    rowDeletingId,
    lastError,
    fetchList,
    removeById,
    removeMany,
    deletableIds,
    reset,
  }
})
