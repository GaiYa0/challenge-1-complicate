import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  fetchUserProfile,
  getHealth,
  login as loginRequest,
  type LoginPayload,
  type UserProfile,
} from '../api/user'
import { TENANT_STORAGE_KEY, TOKEN_STORAGE_KEY } from '../constants/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_STORAGE_KEY))
  /** 与后端 RBAC + 租户对齐的当前用户 */
  const userInfo = ref<UserProfile | null>(null)
  const healthStatus = ref<string | null>(null)

  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  function hydrateFromStorage() {
    token.value = localStorage.getItem(TOKEN_STORAGE_KEY)
  }

  function persistTenant(tenantId: string) {
    localStorage.setItem(TENANT_STORAGE_KEY, tenantId)
  }

  function clearTenant() {
    localStorage.removeItem(TENANT_STORAGE_KEY)
  }

  async function fetchProfile() {
    const p = await fetchUserProfile()
    userInfo.value = p
    persistTenant(p.tenant_id)
    return p
  }

  async function fetchHealth() {
    const h = await getHealth()
    healthStatus.value = h.status
    return h
  }

  async function login(payload: LoginPayload) {
    const res = await loginRequest(payload)
    token.value = res.access_token
    localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token)
    try {
      await fetchProfile()
    } catch (e) {
      token.value = null
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      clearTenant()
      throw e
    }
    return res
  }

  function logout() {
    token.value = null
    userInfo.value = null
    healthStatus.value = null
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    clearTenant()
  }

  return {
    token,
    userInfo,
    healthStatus,
    isAdmin,
    login,
    logout,
    fetchProfile,
    fetchHealth,
    hydrateFromStorage,
  }
})
