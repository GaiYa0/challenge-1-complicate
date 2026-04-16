/**
 * 全局请求 loading（与 axios client 中计数联动）。
 */
import { globalHttpContext } from '../state/httpContext'

export function useGlobalLoading() {
  return {
    isLoading: globalHttpContext.isGlobalLoading,
    loadingCount: globalHttpContext.loadingCount,
    lastRequestId: globalHttpContext.lastRequestId,
  }
}
