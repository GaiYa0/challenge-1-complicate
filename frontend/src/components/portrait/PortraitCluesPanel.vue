<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { PortraitClueItem } from '../../api/portrait'
import StatusTag from '../common/StatusTag.vue'

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
      <span class="panel-title">异常线索列表</span>
    </template>
    <p v-if="clues.length === 0" class="empty-hint">暂无异常线索</p>
    <template v-else>
      <p class="hint">点击行可查看线索详情，包含来源规则和数据依据</p>
      <el-table
        :data="clues"
        stripe
        class="table"
        @row-click="rowClick"
      >
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="类别" width="100" />
        <el-table-column label="风险等级" width="100">
          <template #default="{ row }">
            <StatusTag :raw="row.risk_level" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="风险评分" width="88">
          <template #default="{ row }">{{ row.risk_score?.toFixed(0) ?? '—' }}</template>
        </el-table-column>
      </el-table>
    </template>
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
.empty-hint {
  font-size: 13px;
  color: var(--app-text-secondary);
  text-align: center;
  padding: 20px 0;
}
.table :deep(.el-table__row) {
  cursor: pointer;
}
</style>
