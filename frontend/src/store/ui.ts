import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 全局 UI：页面级 loading（路由切换）、可与按钮/区块 loading 组合使用。
 */
export const useUiStore = defineStore('ui', () => {
  const pageLoading = ref(false)

  function startPageLoading() {
    pageLoading.value = true
  }

  function endPageLoading() {
    pageLoading.value = false
  }

  return {
    pageLoading,
    startPageLoading,
    endPageLoading,
  }
})
