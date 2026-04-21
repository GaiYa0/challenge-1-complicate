/**
 * 离开前未保存提示 (#15)。
 *
 * - `beforeunload`：关闭页签或刷新；
 * - `router.beforeEach`：站内路由切换；
 * 两层都会弹 confirm。视图只需传入 `dirty` ref/getter 与可选 message。
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

export interface UnsavedGuardOptions {
  message?: string
  /** 返回 true 时跳过拦截（例如已经显式确认保存完成） */
  bypass?: () => boolean
}

export function useUnsavedGuard(dirty: Ref<boolean> | (() => boolean), opts: UnsavedGuardOptions = {}) {
  const message = opts.message ?? '有未保存的修改，确定离开当前页面吗？'

  function isDirty(): boolean {
    try {
      if (opts.bypass && opts.bypass()) return false
      const v = typeof dirty === 'function' ? dirty() : dirty.value
      return Boolean(v)
    } catch {
      return false
    }
  }

  function beforeUnload(e: BeforeUnloadEvent) {
    if (!isDirty()) return
    e.preventDefault()
    e.returnValue = message
    return message
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', beforeUnload)
  }

  onBeforeUnmount(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', beforeUnload)
    }
  })

  try {
    onBeforeRouteLeave((_to, _from, next) => {
      if (!isDirty()) return next()
      // eslint-disable-next-line no-alert
      const ok = typeof window !== 'undefined' ? window.confirm(message) : true
      next(ok)
    })
  } catch {
    /* 在非路由上下文中调用时安全 no-op */
  }

  // 保留给外部手动触发重新评估（仅用于触发响应式）
  watch(
    () => (typeof dirty === 'function' ? dirty() : dirty.value),
    () => { /* no-op，watch 只是激活响应式 */ },
  )
}
