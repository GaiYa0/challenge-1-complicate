/**
 * IntersectionObserver 驱动的可视懒渲染（#10 图表懒挂载）。
 *
 * - 首屏外的 ECharts 图表只在滚入视口后才调用 `init`，缓解一次性 mount 卡顿；
 * - `once: true`（默认）保证进入视口一次后不再反复触发。
 *
 * 用法：
 * ```ts
 * const rootRef = ref<HTMLElement>()
 * const { visible } = useLazyRender(rootRef)
 * // v-if="visible"
 * ```
 */
import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

export interface LazyRenderOptions {
  rootMargin?: string
  threshold?: number
  once?: boolean
  /** 不支持 IntersectionObserver 时直接视为可见 */
  fallbackVisible?: boolean
}

export function useLazyRender(
  target: Ref<HTMLElement | null | undefined>,
  opts: LazyRenderOptions = {},
) {
  const { rootMargin = '120px', threshold = 0.01, once = true, fallbackVisible = true } = opts
  const visible = ref(false)

  let observer: IntersectionObserver | null = null

  function cleanup() {
    try {
      observer?.disconnect()
    } catch { /* noop */ }
    observer = null
  }

  function attach(el: HTMLElement) {
    if (typeof IntersectionObserver === 'undefined') {
      visible.value = fallbackVisible
      return
    }
    cleanup()
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            visible.value = true
            if (once) cleanup()
            break
          }
        }
      },
      { rootMargin, threshold },
    )
    observer.observe(el)
  }

  watch(
    target,
    (el) => {
      cleanup()
      if (el) attach(el)
    },
    { immediate: true, flush: 'post' },
  )

  onBeforeUnmount(cleanup)

  return { visible }
}
