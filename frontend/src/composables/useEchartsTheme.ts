/**
 * 订阅 `theme:change` 事件，收敛 ECharts 组件"换主题"的重建逻辑。
 *
 * 用法：
 * ```ts
 * const { themeName, onThemeChange } = useEchartsTheme()
 * let chart: ECharts | null = null
 * function mount() { chart = echarts.init(el, themeName.value) }
 * onThemeChange(() => {
 *   chart?.dispose()
 *   mount()
 *   apply()
 * })
 * ```
 */
import { onBeforeUnmount, ref } from 'vue'
import { currentEchartsTheme } from '../utils/echarts'

export function useEchartsTheme() {
  const themeName = ref<string>(currentEchartsTheme())

  function onThemeChange(handler: (mode: 'light' | 'dark') => void) {
    if (typeof window === 'undefined') return
    const listener = (e: Event) => {
      const detail = (e as CustomEvent<{ mode: 'light' | 'dark' }>).detail
      themeName.value = currentEchartsTheme()
      try {
        handler(detail?.mode ?? 'light')
      } catch (err) {
        console.warn('[useEchartsTheme] handler error', err)
      }
    }
    window.addEventListener('theme:change', listener)
    onBeforeUnmount(() => {
      window.removeEventListener('theme:change', listener)
    })
  }

  return { themeName, onThemeChange }
}
