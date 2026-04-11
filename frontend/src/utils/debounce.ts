export interface DebouncedFn<Args extends unknown[]> {
  (...args: Args): void
  cancel(): void
}

export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number,
): DebouncedFn<Args> {
  let t: ReturnType<typeof setTimeout> | undefined
  const debounced = (...args: Args) => {
    if (t) clearTimeout(t)
    t = setTimeout(() => {
      t = undefined
      fn(...args)
    }, waitMs)
  }
  debounced.cancel = () => {
    if (t) {
      clearTimeout(t)
      t = undefined
    }
  }
  return debounced
}
