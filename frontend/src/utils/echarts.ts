/**
 * 中心化 ECharts 按需注册 + 双主题：
 *
 * 只打包实际使用的 charts / components / renderers / features，
 * 替代旧的 `import * as echarts from 'echarts'`（会打全量 ~600KB gzip）。
 *
 * - 新增图表类型时请在本文件加一行 use(...)；业务代码继续从这里 import echarts。
 * - 注册 `investigation-light` / `investigation-dark` 两套主题，
 *   业务侧 `echarts.init(el, currentThemeName)`；换暗色一次到位。
 * - `init` / `ECharts` / `EChartsOption` 类型都从本模块复用，业务侧无需改动。
 */

import * as echarts from 'echarts/core'

import {
  BarChart,
  CustomChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  PieChart,
  RadarChart,
  ScatterChart,
} from 'echarts/charts'

import {
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  PolarComponent,
  RadarComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  TransformComponent,
  VisualMapComponent,
} from 'echarts/components'

import { LabelLayout, UniversalTransition } from 'echarts/features'

import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  CustomChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  PieChart,
  RadarChart,
  ScatterChart,
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  PolarComponent,
  RadarComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  TransformComponent,
  VisualMapComponent,
  LabelLayout,
  UniversalTransition,
  CanvasRenderer,
])

export const ECHARTS_THEME_LIGHT = 'investigation-light'
export const ECHARTS_THEME_DARK = 'investigation-dark'

echarts.registerTheme(ECHARTS_THEME_LIGHT, {
  color: ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#475569'],
  backgroundColor: 'transparent',
  textStyle: {
    color: '#1f2937',
    fontFamily: 'system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  title: { textStyle: { color: '#1f2937', fontWeight: 600 }, subtextStyle: { color: '#6b7280' } },
  legend: { textStyle: { color: '#4b5563' } },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#cbd5e1' } },
    axisTick: { lineStyle: { color: '#cbd5e1' } },
    axisLabel: { color: '#4b5563' },
    splitLine: { lineStyle: { color: '#e5e7eb' } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: '#cbd5e1' } },
    axisLabel: { color: '#4b5563' },
    splitLine: { lineStyle: { color: '#e5e7eb' } },
  },
  tooltip: {
    backgroundColor: 'rgba(255,255,255,0.98)',
    borderColor: '#e5e7eb',
    borderWidth: 1,
    textStyle: { color: '#1f2937' },
  },
  line: { lineStyle: { width: 2 }, symbolSize: 6, smooth: false },
  bar: { itemStyle: { borderRadius: [4, 4, 0, 0] } },
  pie: { label: { color: '#4b5563' } },
})

echarts.registerTheme(ECHARTS_THEME_DARK, {
  color: ['#60a5fa', '#4ade80', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#f472b6', '#94a3b8'],
  backgroundColor: 'transparent',
  textStyle: {
    color: '#e5e7eb',
    fontFamily: 'system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  title: { textStyle: { color: '#f1f5f9', fontWeight: 600 }, subtextStyle: { color: '#94a3b8' } },
  legend: { textStyle: { color: '#cbd5e1' } },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#334155' } },
    axisTick: { lineStyle: { color: '#334155' } },
    axisLabel: { color: '#cbd5e1' },
    splitLine: { lineStyle: { color: '#1e293b' } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: '#334155' } },
    axisLabel: { color: '#cbd5e1' },
    splitLine: { lineStyle: { color: '#1e293b' } },
  },
  tooltip: {
    backgroundColor: 'rgba(15,23,42,0.96)',
    borderColor: '#334155',
    borderWidth: 1,
    textStyle: { color: '#f1f5f9' },
  },
  line: { lineStyle: { width: 2 }, symbolSize: 6, smooth: false },
  bar: { itemStyle: { borderRadius: [4, 4, 0, 0] } },
  pie: { label: { color: '#cbd5e1' } },
})

/** 视图层通过本函数拿到当前 ECharts 主题名，init 时传入即可同步暗色。*/
export function currentEchartsTheme(): string {
  if (typeof document === 'undefined') return ECHARTS_THEME_LIGHT
  return document.documentElement.classList.contains('dark')
    ? ECHARTS_THEME_DARK
    : ECHARTS_THEME_LIGHT
}

export type { ECharts, EChartsType } from 'echarts/core'
export type { EChartsOption } from 'echarts'
export { echarts }
export default echarts
