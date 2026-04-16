<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { PortraitClueItem } from '../../api/portrait'

const props = defineProps<{
  caseId: number
  clues: PortraitClueItem[]
}>()

const router = useRouter()

function rowClick(row: PortraitClueItem) {
  void router.push({
    name: 'ClueDetail',
    params: { caseId: String(props.caseId), clueId: String(row.id) },
  })
}
</script>

<template>
  <el-card class="panel" shadow="never">
    <template #header>
      <span class="panel-title">异常行为 · 线索列表</span>
    </template>
    <p class="hint">点击行跳转线索详情</p>
    <el-table
      :data="clues"
      stripe
      class="table"
      @row-click="rowClick"
    >
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column prop="risk_level" label="风险等级" width="100" />
      <el-table-column prop="risk_score" label="评分" width="88">
        <template #default="{ row }">{{ row.risk_score.toFixed(0) }}</template>
      </el-table-column>
    </el-table>
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
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0 0 10px;
}
.table :deep(.el-table__row) {
  cursor: pointer;
}
</style>
