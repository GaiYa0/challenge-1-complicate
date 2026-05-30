<script setup lang="ts">
/**
 * 证据详情面板 — 右侧抽屉
 * 展示单条证据的完整信息：来源、命中规则、原始记录、备注
 * 支持证据链上下文展示
 */
import { computed } from 'vue'
import type { Evidence, ActionType } from '../../types/evidence'
import { ACTION_TYPE_LABELS } from '../../types/evidence'
import { getFieldLabel } from '../../utils/fieldLabels'

const props = defineProps<{
  visible: boolean
  evidence: Evidence | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update:remark', val: string): void
  (e: 'update:status', val: Evidence['status']): void
}>()

const localRemark = computed({
  get: () => props.evidence?.remark ?? '',
  set: (v) => emit('update:remark', v),
})

const formattedRawContent = computed(() => {
  const raw = props.evidence?.rawContent ?? ''
  if (!raw) return '无原始记录'
  return raw
    .split('\n')
    .map((line) => {
      const idx = line.indexOf(':')
      if (idx <= 0) return line
      const key = line.slice(0, idx).trim()
      const value = line.slice(idx + 1)
      return `${getFieldLabel(key)}:${value}`
    })
    .join('\n')
})

function statusLabel(s: string): string {
  if (s === 'confirmed') return '已确认'
  if (s === 'pending') return '待确认'
  return '已排除'
}

function statusType(s: string): 'success' | 'warning' | 'info' {
  if (s === 'confirmed') return 'success'
  if (s === 'pending') return 'warning'
  return 'info'
}

function sourceTypeLabel(s: string): string {
  return ACTION_TYPE_LABELS[s as ActionType] ?? s
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    title="证据详情"
    direction="rtl"
    size="460px"
    @close="emit('close')"
    :close-on-click-modal="true"
    class="evidence-drawer"
  >
    <div v-if="!evidence" class="panel-empty">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="22" stroke="#e5e7eb" stroke-width="2" />
          <path d="M16 24h16M24 16v16" stroke="#d1d5db" stroke-width="2" stroke-linecap="round" />
        </svg>
      </div>
      <p>请从证据关系图中选择一条证据查看详情</p>
    </div>
    <div v-else class="panel-body">
      <!-- 证据状态 -->
      <div class="panel-section">
        <h4 class="section-label">证据状态</h4>
        <div class="status-row">
          <el-tag :type="statusType(evidence.status)" effect="dark" size="default">
            {{ statusLabel(evidence.status) }}
          </el-tag>
          <span class="evidence-id">{{ evidence.recordId }}</span>
        </div>
        <div class="status-actions">
          <el-button
            v-if="evidence.status !== 'confirmed'"
            size="small"
            type="success"
            plain
            @click="emit('update:status', 'confirmed')"
          >
            标记为已确认
          </el-button>
          <el-button
            v-if="evidence.status !== 'pending'"
            size="small"
            type="warning"
            plain
            @click="emit('update:status', 'pending')"
          >
            标记为待确认
          </el-button>
          <el-button
            v-if="evidence.status !== 'rejected'"
            size="small"
            type="info"
            plain
            @click="emit('update:status', 'rejected')"
          >
            排除
          </el-button>
        </div>
      </div>

      <!-- 数据来源 -->
      <div class="panel-section">
        <h4 class="section-label">数据来源</h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-key">来源系统</span>
            <span class="info-val">{{ evidence.source || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">来源类型</span>
            <el-tag size="small" :type="evidence.sourceType === 'fund' ? 'danger' : evidence.sourceType === 'call' ? 'warning' : 'primary'" effect="plain">
              {{ sourceTypeLabel(evidence.sourceType) }}
            </el-tag>
          </div>
          <div class="info-item">
            <span class="info-key">记录编号</span>
            <span class="info-val mono">{{ evidence.recordId || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">采集时间</span>
            <span class="info-val mono">{{ evidence.time || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 证据链位置 -->
      <div class="panel-section">
        <h4 class="section-label">证据链位置</h4>
        <div class="chain-context">
          <div class="chain-step">
            <span class="cs-dot cs-dot--suspect" />
            <span>嫌疑人执行行为</span>
          </div>
          <div class="chain-arrow" />
          <div class="chain-step">
            <span class="cs-dot cs-dot--action" />
            <span>{{ sourceTypeLabel(evidence.sourceType) }}</span>
          </div>
          <div class="chain-arrow" />
          <div class="chain-step chain-step--active">
            <span class="cs-dot cs-dot--evidence" />
            <span>当前证据</span>
          </div>
          <div class="chain-arrow" />
          <div class="chain-step">
            <span class="cs-dot cs-dot--person" />
            <span>关联人</span>
          </div>
        </div>
      </div>

      <!-- 命中规则 -->
      <div class="panel-section">
        <h4 class="section-label">命中规则</h4>
        <div class="rule-box">
          {{ evidence.ruleHit || '无命中规则' }}
        </div>
      </div>

      <!-- 原始记录 -->
      <div class="panel-section">
        <h4 class="section-label">原始记录</h4>
        <pre class="raw-content">{{ formattedRawContent }}</pre>
      </div>

      <!-- 备注 -->
      <div class="panel-section">
        <h4 class="section-label">备注（用于定罪参考）</h4>
        <el-input
          v-model="localRemark"
          type="textarea"
          :rows="3"
          placeholder="添加备注..."
        />
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.panel-empty {
  text-align: center;
  padding: 80px 20px;
  color: var(--app-text-secondary);
}
.empty-icon-wrap { margin-bottom: 16px; }
.panel-body {
  padding: 0 4px;
}
.panel-section {
  margin-bottom: 22px;
}
.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-secondary);
  margin: 0 0 8px;
  letter-spacing: 0.5px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.evidence-id {
  font-size: 11px;
  font-family: 'SF Mono', 'Menlo', monospace;
  color: var(--app-text-secondary);
}
.status-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.info-key {
  font-size: 11px;
  color: var(--app-text-secondary);
  font-weight: 500;
}
.info-val {
  font-size: 14px;
  color: var(--app-text);
  font-weight: 500;
}
.mono { font-family: 'SF Mono', 'Menlo', monospace; font-size: 13px; }

/* 证据链上下文 */
.chain-context {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 12px;
  background: var(--app-bg-layout);
  border: 1px solid var(--app-border);
  border-radius: 8px;
  overflow-x: auto;
}
.chain-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--app-text-secondary);
  white-space: nowrap;
  padding: 4px 8px;
  border-radius: 4px;
}
.chain-step--active {
  background: rgba(202, 138, 4, 0.1);
  border: 1px solid rgba(202, 138, 4, 0.3);
  color: #854d0e;
  font-weight: 600;
}
.cs-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.cs-dot--suspect { background: #dc2626; }
.cs-dot--action { background: #2563eb; }
.cs-dot--evidence { background: #ca8a04; }
.cs-dot--person { background: #6b7280; }
.chain-arrow {
  width: 20px;
  height: 1px;
  background: var(--app-border);
  flex-shrink: 0;
  position: relative;
}
.chain-arrow::after {
  content: '';
  position: absolute;
  right: 0;
  top: -3px;
  border: 3px solid transparent;
  border-left-color: var(--app-border);
}

.rule-box {
  padding: 12px 14px;
  background: rgba(202, 138, 4, 0.06);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 6px;
  font-size: 14px;
  color: #854d0e;
  line-height: 1.6;
}
.raw-content {
  padding: 12px 14px;
  background: var(--app-bg-layout);
  border: 1px solid var(--app-border);
  border-radius: 6px;
  font-size: 12px;
  color: var(--app-text);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  font-family: 'SF Mono', 'Menlo', monospace;
}
</style>
