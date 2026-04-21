<script setup lang="ts">
import type { PortraitEconomic } from '../../api/portrait'
import FormatAmount from '../common/FormatAmount.vue'
import CountUp from '../common/CountUp.vue'

defineProps<{
  data: PortraitEconomic
}>()
</script>

<template>
  <el-card class="panel" shadow="never">
    <template #header>
      <span class="panel-title">经济状况</span>
    </template>
    <p class="explain">{{ data.explain }}</p>
    <div class="stats">
      <div class="stat">
        <div class="label">总交易额（估算）</div>
        <div class="value">
          <FormatAmount :value="data.total_amount" :fraction-digits="0" animate compact />
        </div>
      </div>
      <div class="stat">
        <div class="label">
          异常线索占比
          <span class="ratio-value">{{ Math.round(data.anomaly_ratio * 100) }}%</span>
        </div>
        <el-progress
          :percentage="Math.round(data.anomaly_ratio * 100)"
          :stroke-width="14"
          :show-text="false"
          :color="data.anomaly_ratio > 0.4 ? 'var(--app-danger)' : data.anomaly_ratio > 0.2 ? 'var(--app-warning)' : 'var(--app-success)'"
        />
      </div>
      <div class="stat small">
        <span>转出笔数（图谱）</span>
        <strong><CountUp :value="data.transfer_out_count" /></strong>
      </div>
      <div class="stat small">
        <span>转入笔数（图谱）</span>
        <strong><CountUp :value="data.transfer_in_count" /></strong>
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
.stats {
  display: grid;
  gap: 16px;
}
.stat .label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.stat .value {
  font-size: 22px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.stat .label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stat .ratio-value {
  font-weight: 600;
  color: var(--app-text);
  font-variant-numeric: tabular-nums;
}
.stat.small {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.stat.small strong {
  color: var(--app-text);
  font-variant-numeric: tabular-nums;
}
</style>
