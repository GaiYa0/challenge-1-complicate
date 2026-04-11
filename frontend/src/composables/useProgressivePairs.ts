import { computed, onUnmounted, ref, watch } from 'vue'

/**
 * 将长序列分段“喂给”图表：先渲染前 chunk 点，再在 rAF 中追加，避免首帧卡死。
 * 仍建议配合 downsamplePaired 限制最终点数（如 1000）。
 */
export function useProgressivePairs(
  getLabels: () => string[],
  getValues: () => number[],
  opts: { chunk?: number; enabled: () => boolean } = { enabled: () => false },
) {
  const shown = ref(0)
  let raf = 0

  function cancelRaf() {
    if (raf) cancelAnimationFrame(raf)
    raf = 0
  }

  function pump() {
    cancelRaf()
    const labels = getLabels()
    const values = getValues()
    const n = Math.min(labels.length, values.length)
    const chunk = opts.chunk ?? 200
    if (!opts.enabled() || n === 0) {
      shown.value = n
      return
    }
    shown.value = Math.min(chunk, n)
    const step = () => {
      if (shown.value >= n) return
      shown.value = Math.min(n, shown.value + chunk)
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
  }

  watch(
    () => {
      const l = getLabels()
      const v = getValues()
      return [l, v, opts.enabled() ? 1 : 0] as const
    },
    () => pump(),
    { immediate: true },
  )

  onUnmounted(() => cancelRaf())

  const labels = computed(() => getLabels().slice(0, shown.value))
  const values = computed(() => getValues().slice(0, shown.value))

  return { labels, values }
}
