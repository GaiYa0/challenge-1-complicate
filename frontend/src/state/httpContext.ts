/**
 * HTTP 层与 UI 解耦的全局状态（不依赖 Pinia 初始化顺序，供 axios 拦截器使用）。
 * 页面级 loading 仍由各 store / 组件自行维护；此处仅服务「全局请求计数」与 request_id 透传。
 */

import { computed, ref } from 'vue'

const loadingCount = ref(0)
const lastRequestId = ref<string | null>(null)

export const globalHttpContext = {
  loadingCount,
  /** 是否存在未完成的、计入全局计数的请求 */
  isGlobalLoading: computed(() => loadingCount.value > 0),
  lastRequestId,

  startRequest(): void {
    loadingCount.value += 1
  },

  endRequest(): void {
    loadingCount.value = Math.max(0, loadingCount.value - 1)
  },

  setLastRequestId(id: string | null): void {
    lastRequestId.value = id
  },
}
