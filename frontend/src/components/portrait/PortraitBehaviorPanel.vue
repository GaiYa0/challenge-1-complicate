<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed } from 'vue'
import type { PortraitBehavior } from '../../api/portrait'
import BaseChart from '../charts/BaseChart.vue'
import { buildBehaviorTimelineOption, buildPortraitMapOption } from '../../utils/portraitCharts'

const props = defineProps<{
  data: PortraitBehavior
}>()

const optTimeline = computed<EChartsOption>(() =>
  buildBehaviorTimelineOption(props.data.timeline_bins),
)
const optMap = computed<EChartsOption>(() => buildPortraitMapOption(props.data))
</script>

<template>
  <el-card class="panel" shadow="never">
    <template #header>
      <span class="panel-title">行为轨迹</span>
    </template>
    <p class="explain">{{ data.explain }}</p>
    <div class="split">
      <div class="chart-block">
        <BaseChart class="chart-timeline" :option="optTimeline" />
      </div>
      <div class="chart-block">
        <BaseChart class="chart-map" :option="optMap" />
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.panel {
  border-radius: 8px;
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
}
.explain {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
  line-height: 1.5;
}
.split {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 16px;
}
@media (max-width: 960px) {
  .split {
    grid-template-columns: 1fr;
  }
}
.chart-timeline :deep(.base-chart-host) {
  height: 300px;
}
.chart-map :deep(.base-chart-host) {
  height: 360px;
}
</style>
