<script setup lang="ts">
/**
 * 证据链时间轴 — 核心组件
 * 结构：[时间] → [行为] → [证据] → [影响对象]
 */
import { computed, ref } from 'vue'
import type {
  EvidenceChainEntry,
  Evidence,
  ActionType,
} from '../../types/evidence'
import { ACTION_TYPE_LABELS } from '../../types/evidence'

const props = defineProps<{
  entries: EvidenceChainEntry[]
  filterType?: ActionType | 'all'
  filterPerson?: string
}>()

const emit = defineEmits<{
  (e: 'select-evidence', ev: Evidence): void
  (e: 'select-person', personId: string): void
}>()

const expandedEntries = ref<Set<string>>(new Set())

function toggleEntry(id: string) {
  if (expandedEntries.value.has(id)) {
    expandedEntries.value.delete(id)
  } else {
    expandedEntries.value.add(id)
  }
}

const filteredEntries = computed(() => {
  let list = props.entries
  if (props.filterType && props.filterType !== 'all') {
    list = list.filter((e) => e.action.type === props.filterType)
  }
  if (props.filterPerson) {
    const p = props.filterPerson.toLowerCase()
    list = list.filter((e) =>
      e.relatedPersons.some((rp) => rp.name.toLowerCase().includes(p)),
    )
  }
  return list
})

function formatTime(ts: string): string {
  if (!ts) return '--'
  return ts.replace('T', ' ').slice(0, 16)
}

function actionIcon(type: ActionType): string {
  switch (type) {
    case 'fund': return '\u5143'
    case 'call': return '\u8BDD'
    case 'trip': return '\u8F68'
    default: return '\u2022'
  }
}

function statusClass(status: string): string {
  if (status === 'confirmed') return 'evidence-confirmed'
  if (status === 'pending') return 'evidence-pending'
  return 'evidence-rejected'
}
</script>

<template>
  <div class="evidence-timeline">
    <div v-if="filteredEntries.length === 0" class="timeline-empty">
      <p>暂无证据链数据</p>
    </div>
    <div
      v-for="entry in filteredEntries"
      :key="entry.action.id"
      :id="`timeline-entry-${entry.action.id}`"
      class="timeline-item"
      :class="{ 'timeline-item--expanded': expandedEntries.has(entry.action.id) }"
    >
      <div class="timeline-dot" :class="`dot-${entry.action.type}`">
        <span class="dot-icon">{{ actionIcon(entry.action.type) }}</span>
      </div>
      <div class="timeline-connector" />

      <div class="timeline-content" @click="toggleEntry(entry.action.id)">
        <div class="timeline-header">
          <span class="timeline-time">{{ formatTime(entry.time) }}</span>
          <el-tag size="small" :type="entry.action.type === 'fund' ? 'danger' : entry.action.type === 'call' ? 'warning' : 'info'" effect="plain">
            {{ ACTION_TYPE_LABELS[entry.action.type] || entry.action.type }}
          </el-tag>
        </div>

        <div class="timeline-action">
          <span class="action-label">{{ entry.action.label }}</span>
          <span v-if="entry.action.amount" class="action-amount">{{ entry.action.amount.toLocaleString() }} 元</span>
        </div>
        <p class="action-desc">{{ entry.action.description }}</p>

        <div class="timeline-evidence-summary">
          <span class="evidence-count">{{ entry.evidences.length }} 条证据</span>
          <span v-if="entry.relatedPersons.length > 0" class="person-count">
            {{ entry.relatedPersons.length }} 名关联人
          </span>
          <span class="expand-hint">{{ expandedEntries.has(entry.action.id) ? '收起' : '展开详情' }}</span>
        </div>

        <transition name="slide-down">
          <div v-if="expandedEntries.has(entry.action.id)" class="timeline-detail">
            <div v-if="entry.fundTxRows?.length" class="detail-section">
              <h4 class="detail-title">逐笔转账</h4>
              <p
                v-if="entry.fundLineTxCount != null && entry.fundTxRows && entry.fundLineTxCount > entry.fundTxRows.length"
                class="fund-tx-capped-hint"
              >
                汇总共 {{ entry.fundLineTxCount }} 笔；下列为后端返回的逐笔（受条数上限，已截断）。
              </p>
              <div class="fund-tx-header">
                <span>时间</span>
                <span>金额（元）</span>
              </div>
              <div class="fund-tx-scroll">
                <div
                  v-for="(row, idx) in entry.fundTxRows"
                  :key="`ftx-${entry.action.id}-${idx}`"
                  class="fund-tx-row"
                >
                  <span class="fund-tx-time">{{ formatTime((row.time && String(row.time)) || '') }}</span>
                  <span class="fund-tx-amt">{{ row.amount.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) }}</span>
                </div>
              </div>
            </div>
            <div class="detail-section">
              <h4 class="detail-title">证据材料</h4>
              <div
                v-for="ev in entry.evidences"
                :key="ev.id"
                class="evidence-item"
                :class="statusClass(ev.status)"
                @click.stop="emit('select-evidence', ev)"
              >
                <div class="ev-header">
                  <span class="ev-source">{{ ev.source }}</span>
                  <el-tag size="small" :type="ev.status === 'confirmed' ? 'success' : ev.status === 'pending' ? 'warning' : 'info'" effect="light">
                    {{ ev.status === 'confirmed' ? '已确认' : ev.status === 'pending' ? '待确认' : '已排除' }}
                  </el-tag>
                </div>
                <div class="ev-body">
                  <span class="ev-rule">命中规则: {{ ev.ruleHit || '--' }}</span>
                  <span class="ev-record">记录编号: {{ ev.recordId || '--' }}</span>
                </div>
                <div v-if="ev.remark" class="ev-remark">备注: {{ ev.remark }}</div>
              </div>
            </div>

            <div v-if="entry.relatedPersons.length > 0" class="detail-section">
              <h4 class="detail-title">影响对象</h4>
              <div
                v-for="rp in entry.relatedPersons"
                :key="rp.id"
                class="related-person"
                @click.stop="emit('select-person', rp.id)"
              >
                <span class="rp-name">{{ rp.name }}</span>
                <span class="rp-role">{{ rp.role }}</span>
                <span class="rp-relation">{{ rp.relation }}</span>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.evidence-timeline {
  position: relative;
  padding-left: 40px;
}
.timeline-empty {
  text-align: center;
  padding: 40px 0;
  color: var(--app-text-secondary);
}
.timeline-item {
  position: relative;
  padding-bottom: 24px;
}
.timeline-item:last-child { padding-bottom: 0; }
.timeline-item:last-child .timeline-connector { display: none; }
.timeline-dot {
  position: absolute;
  left: -40px;
  top: 4px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  z-index: 2;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
.dot-icon { line-height: 1; }
.dot-fund { background: #fecaca; color: #dc2626; border: 2px solid #dc2626; }
.dot-call { background: #fed7aa; color: #ea580c; border: 2px solid #ea580c; }
.dot-trip { background: #bfdbfe; color: #2563eb; border: 2px solid #2563eb; }
.dot-other { background: #e5e7eb; color: #6b7280; border: 2px solid #6b7280; }
.timeline-connector {
  position: absolute;
  left: -24px;
  top: 36px;
  bottom: 0;
  width: 2px;
  background: var(--app-border);
}
.timeline-content {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 14px 18px;
  cursor: pointer;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.timeline-content:hover {
  border-color: var(--app-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.timeline-item--expanded .timeline-content {
  border-color: var(--app-primary);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
.timeline-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.timeline-time {
  font-size: 13px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.timeline-action {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 4px;
}
.action-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}
.action-amount {
  font-size: 15px;
  font-weight: 700;
  color: #dc2626;
  font-variant-numeric: tabular-nums;
}
.action-desc {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0 0 8px;
  line-height: 1.5;
}
.timeline-evidence-summary {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.evidence-count {
  background: #fef08a;
  color: #854d0e;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.person-count {
  background: #e5e7eb;
  color: #374151;
  padding: 2px 8px;
  border-radius: 4px;
}
.expand-hint {
  margin-left: auto;
  color: var(--app-primary);
  font-weight: 500;
}
.timeline-detail {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--app-border);
}
.detail-section { margin-bottom: 14px; }
.detail-section:last-child { margin-bottom: 0; }
.fund-tx-capped-hint {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin: 0 0 8px;
  line-height: 1.4;
}
.fund-tx-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  padding: 6px 10px 4px;
  border-bottom: 1px solid var(--app-border);
}
.fund-tx-header span:first-child { flex: 1; min-width: 0; }
.fund-tx-header span:last-child { flex-shrink: 0; text-align: right; margin-left: 12px; }
.fund-tx-scroll {
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-bg-layout);
}
.fund-tx-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--app-border);
}
.fund-tx-row:last-child { border-bottom: none; }
.fund-tx-time {
  font-variant-numeric: tabular-nums;
  color: var(--app-text);
  min-width: 0;
  flex: 1;
}
.fund-tx-amt {
  font-weight: 600;
  color: #dc2626;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.detail-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 8px;
}
.evidence-item {
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s;
}
.evidence-item:hover { background: var(--app-bg-layout); }
.evidence-confirmed { border-left-color: #16a34a; background: rgba(22, 163, 74, 0.04); }
.evidence-pending { border-left-color: #ca8a04; background: rgba(202, 138, 4, 0.04); }
.evidence-rejected { border-left-color: #6b7280; background: rgba(107, 114, 128, 0.04); }
.ev-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.ev-source {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
}
.ev-body {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.ev-remark {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin-top: 4px;
  font-style: italic;
}
.related-person {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  background: var(--app-bg-layout);
  cursor: pointer;
  transition: background 0.15s;
}
.related-person:hover { background: var(--app-border); }
.rp-name { font-weight: 600; color: var(--app-text); font-size: 14px; }
.rp-role { font-size: 12px; color: var(--app-text-secondary); }
.rp-relation { font-size: 12px; color: var(--app-primary); margin-left: auto; }
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
