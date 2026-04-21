/**
 * 全局主题 store：明 / 暗 切换。
 *
 * - 持久化到 localStorage；初始值优先读存储，其次 `prefers-color-scheme`。
 * - 切换时：
 *   1. toggle `html.dark` class（Element Plus 官方暗色支持）
 *   2. 触发自定义事件 `theme:change`，ECharts/G6 组件监听后重建或 setTheme
 * - 视图层只 read/toggle，不直接操作 DOM。
 */
import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'app.theme'

function resolveInitial(): ThemeMode {
  if (typeof window === 'undefined') return 'light'
  const saved = window.localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

function applyTheme(mode: ThemeMode): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (mode === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
  root.setAttribute('data-theme', mode)
  window.dispatchEvent(new CustomEvent('theme:change', { detail: { mode } }))
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(resolveInitial())
  applyTheme(mode.value)

  watch(mode, (next) => {
    if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, next)
    applyTheme(next)
  })

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function set(next: ThemeMode) {
    mode.value = next
  }

  return { mode, toggle, set }
})
