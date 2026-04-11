/**
 * 将 (labels, values) 成对抽样到不超过 maxPoints。
 * 等步长取点并保留首尾，降低 ECharts 绘制与 diff 成本。
 */
export function downsamplePaired(
  labels: string[],
  values: number[],
  maxPoints: number,
): { labels: string[]; values: number[] } {
  const n = Math.min(labels.length, values.length)
  if (n <= maxPoints) {
    return { labels: labels.slice(0, n), values: values.slice(0, n) }
  }
  const step = Math.ceil(n / maxPoints)
  const outL: string[] = []
  const outV: number[] = []
  for (let i = 0; i < n; i += step) {
    outL.push(labels[i]!)
    outV.push(values[i]!)
  }
  const last = n - 1
  if (outL[outL.length - 1] !== labels[last]) {
    outL.push(labels[last]!)
    outV.push(values[last]!)
  }
  if (outL.length > maxPoints) {
    return downsamplePaired(outL, outV, maxPoints)
  }
  return { labels: outL, values: outV }
}
