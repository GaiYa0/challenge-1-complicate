export interface ThrottledFn<Args extends unknown[]> {
  (...args: Args): void
  cancel(): void
}

export function throttle<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number,
): ThrottledFn<Args> {
  let last = 0
  let trailingTimer: ReturnType<typeof setTimeout> | undefined
  const throttled = (...args: Args) => {
    const now = Date.now()
    const remain = waitMs - (now - last)
    if (remain <= 0) {
      if (trailingTimer) {
        clearTimeout(trailingTimer)
        trailingTimer = undefined
      }
      last = now
      fn(...args)
      return
    }
    if (!trailingTimer) {
      trailingTimer = setTimeout(() => {
        trailingTimer = undefined
        last = Date.now()
        fn(...args)
      }, remain)
    }
  }
  throttled.cancel = () => {
    if (trailingTimer) {
      clearTimeout(trailingTimer)
      trailingTimer = undefined
    }
  }
  return throttled
}
