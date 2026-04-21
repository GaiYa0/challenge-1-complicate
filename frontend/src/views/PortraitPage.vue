<script setup lang="ts">
/**
 * 证据链视图 — 围绕嫌疑人构建完整证据链
 * 删除：综合评分、风险等级主视觉、纯关系图
 * 结构：嫌疑人信息 → 标签 → 证据链时间轴 → 证据筛选
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useCaseStore } from '../store/case'
import { usePortraitStore } from '../store/modules/portrait.store'
import { useFileStore } from '../store/modules/file.store'
import { notifyError } from '../utils/notify'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import EvidenceTimeline from '../components/evidence/EvidenceTimeline.vue'
import EvidenceGraph from '../components/evidence/EvidenceGraph.vue'
import EvidencePanel from '../components/evidence/EvidencePanel.vue'
import type {
  EvidenceChainEntry,
  Evidence,
  ActionType,
  EvidenceAction,
  EvidenceGraphData,
  EvidenceGraphNode,
  EvidenceGraphEdge,
  EvidenceNodeKind,
  RelatedPerson,
} from '../types/evidence'
import { ACTION_TYPE_LABELS } from '../types/evidence'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const portraitStore = usePortraitStore()
const fileStore = useFileStore()

const { loading, current: portrait, lastError } = storeToRefs(portraitStore)

const caseId = computed(() => Number(route.params.caseId))
const personId = computed(() => decodeURIComponent(String(route.params.personId ?? '')))
const hasData = computed(() => fileStore.items.length > 0)

const filterType = ref<ActionType | 'all'>('all')
const filterPerson = ref('')
const panelVisible = ref(false)
const selectedEvidence = ref<Evidence | null>(null)

async function load(opts?: { force?: boolean }) {
  if (!personId.value || !Number.isFinite(caseId.value)) return
  const result = await portraitStore.load(caseId.value, personId.value, opts)
  if (result === null && lastError.value) {
    notifyError(lastError.value || '加载数据失败')
  }
}

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  await fileStore.fetchList(`case-${caseId.value}`)
  if (hasData.value) {
    void load()
  }
})

const suspectTags = computed<string[]>(() => {
  if (!portrait.value) return []
  const tags: string[] = []
  const eco = portrait.value.economic
  if (eco.anomaly_ratio > 0.3) tags.push('异常资金')
  if (eco.total_amount > 100000) tags.push('大额交易')
  if (eco.transfer_out_count > 10) tags.push('高频转出')
  const clues = portrait.value.clues ?? []
  for (const c of clues) {
    if (c.category === 'fund' && !tags.includes('资金往来')) tags.push('资金往来')
    if (c.category === 'call' && !tags.includes('通话异常')) tags.push('通话异常')
    if (c.category === 'trip' && !tags.includes('出行异常')) tags.push('出行异常')
  }
  if (tags.length === 0) tags.push('待定性')
  return tags
})

const evidenceChainEntries = computed<EvidenceChainEntry[]>(() => {
  if (!portrait.value) return []
  const entries: EvidenceChainEntry[] = []
  const clues = portrait.value.clues ?? []
  const economic = portrait.value.economic
  const fundLines = economic.fund_counterparty_lines ?? []
  const fundOnly = economic.fund_only_evidence === true
  const fundClueCount = clues.filter((c) => c.category === 'fund').length
  const social = portrait.value.social

  const pushRelatedForEvidence = (actionType: ActionType, evId: string) => {
    const relatedPersons: RelatedPerson[] = []
    if (social?.graph?.nodes) {
      const edges = social.graph.edges ?? []
      const centerId = social.center_id
      const connected = edges
        .filter((e) => e.source === centerId || e.target === centerId)
        .slice(0, 3)
      for (const edge of connected) {
        const otherId = edge.source === centerId ? edge.target : edge.source
        const node = social.graph.nodes.find((n) => n.id === otherId)
        if (node) {
          relatedPersons.push({
            id: otherId,
            name: node.label ?? otherId,
            role: '关联人',
            relation: actionType === 'fund' ? '资金往来方' : '联系人',
            evidenceIds: [evId],
          })
        }
      }
    }
    return relatedPersons
  }

  if (fundLines.length > 0) {
    let i = 0
    for (const line of fundLines) {
      i += 1
      const evId = `ev-fund-cp-${i}`
      const actionId = `action-fund-cp-${i}`
      const time = portrait.value.basic_info?.summary?.includes('2024') ? '2024-01-01' : new Date().toISOString().slice(0, 10)
      const action: EvidenceAction = {
        id: actionId,
        type: 'fund',
        label: `${personId.value} → ${line.counterparty}`,
        time,
        description: `共 ${line.tx_count} 笔交易（对手侧账户合并汇总）`,
        amount: line.amount,
      }
      const rowPreview = (line.rows?.length)
        ? `\n逐笔明细(前若干笔): ${line.rows.slice(0, 8).map((r) => r.amount).join(', ')}${line.rows.length > 8 ? '…' : ''}`
        : ''
      const evidences: Evidence[] = [{
        id: evId,
        actionId,
        source: '资金往来系统',
        sourceType: 'fund',
        recordId: `FUND-CP-${i}`,
        ruleHit: '对手侧账户汇总',
        rawContent: `对手: ${line.counterparty}\n金额: ${line.amount}\n笔数: ${line.tx_count}${rowPreview}`,
        remark: '',
        status: 'pending',
        time: action.time,
      }]
      entries.push({
        time: action.time,
        action,
        evidences,
        relatedPersons: pushRelatedForEvidence('fund', evId),
      })
    }
  } else {
    const clueList = fundOnly ? clues.filter((c) => c.category === 'fund') : clues

    for (const clue of clueList) {
      const actionType: ActionType =
        clue.category === 'fund' ? 'fund'
        : clue.category === 'call' ? 'call'
        : clue.category === 'trip' ? 'trip'
        : 'other'

      const action: EvidenceAction = {
        id: `action-${clue.id}`,
        type: actionType,
        label: clue.title,
        time: portrait.value.basic_info?.summary?.includes('2024') ? '2024-01-01' : new Date().toISOString().slice(0, 10),
        description: clue.title,
        amount: actionType === 'fund' ? portrait.value.economic.total_amount / Math.max(1, fundClueCount) : undefined,
      }

      const evId = `ev-${clue.id}`
      const evidences: Evidence[] = [{
        id: evId,
        actionId: action.id,
        source: ACTION_TYPE_LABELS[actionType] + '系统',
        sourceType: actionType,
        recordId: `CLU-${clue.id}`,
        ruleHit: clue.risk_level === 'high' ? '高风险规则命中' : clue.risk_level === 'medium' ? '中风险规则命中' : '低风险规则命中',
        rawContent: `线索标题: ${clue.title}\n风险等级: ${clue.risk_level}\n评分: ${clue.risk_score}`,
        remark: '',
        status: clue.risk_level === 'high' ? 'confirmed' : 'pending',
        time: action.time,
      }]

      entries.push({
        time: action.time,
        action,
        evidences,
        relatedPersons: pushRelatedForEvidence(actionType, evId),
      })
    }
  }

  if (portrait.value.economic && entries.every((e) => e.action.type !== 'fund')) {
    const eco = portrait.value.economic
    if (eco.total_amount > 0) {
      const action: EvidenceAction = {
        id: 'action-eco-summary',
        type: 'fund',
        label: `资金流转总额 ${eco.total_amount.toLocaleString()} 元`,
        time: new Date().toISOString().slice(0, 10),
        description: eco.explain || `转出 ${eco.transfer_out_count} 次，转入 ${eco.transfer_in_count} 次，异常比例 ${(eco.anomaly_ratio * 100).toFixed(1)}%`,
        amount: eco.total_amount,
      }
      entries.unshift({
        time: action.time,
        action,
        evidences: [{
          id: 'ev-eco-summary',
          actionId: action.id,
          source: '资金分析引擎',
          sourceType: 'fund',
          recordId: 'ECO-SUM',
          ruleHit: eco.anomaly_ratio > 0.3 ? '异常比例超过30%' : '资金流转正常',
          rawContent: `总金额: ${eco.total_amount}\n异常比例: ${(eco.anomaly_ratio * 100).toFixed(1)}%\n转出: ${eco.transfer_out_count}\n转入: ${eco.transfer_in_count}`,
          remark: '',
          status: eco.anomaly_ratio > 0.3 ? 'confirmed' : 'pending',
          time: action.time,
        }],
        relatedPersons: [],
      })
    }
  }

  return entries.sort((a, b) => b.time.localeCompare(a.time))
})

const totalEvidenceCount = computed(() =>
  evidenceChainEntries.value.reduce((sum, e) => sum + e.evidences.length, 0),
)
const confirmedCount = computed(() =>
  evidenceChainEntries.value.reduce(
    (sum, e) => sum + e.evidences.filter((ev) => ev.status === 'confirmed').length,
    0,
  ),
)

const highlightChainId = ref<string | null>(null)

const portraitGraphData = computed<EvidenceGraphData | null>(() => {
  if (evidenceChainEntries.value.length === 0) return null
  const nodes: EvidenceGraphNode[] = []
  const edges: EvidenceGraphEdge[] = []

  const suspectId = `suspect-${personId.value}`
  nodes.push({ id: suspectId, kind: 'suspect', label: personId.value })

  for (const entry of evidenceChainEntries.value) {
    const aId = entry.action.id
    nodes.push({
      id: aId,
      kind: 'action',
      label: entry.action.label,
      data: { actionType: entry.action.type, time: entry.time },
    })
    edges.push({ id: `e-s-${aId}`, source: suspectId, target: aId, label: '', actionType: entry.action.type })

    const amt = entry.action.amount
    for (const ev of entry.evidences) {
      nodes.push({
        id: ev.id,
        kind: 'evidence',
        label: ev.source,
        data: { sourceLabel: ev.source, targetLabel: '', actionType: ev.sourceType },
      })
      edges.push({
        id: `e-a-${ev.id}`,
        source: aId,
        target: ev.id,
        label: amt != null ? `${amt.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}元` : '产生证据',
        actionType: entry.action.type,
        weight: amt,
      })
    }
  }
  return { nodes, edges }
})

function handleSelectEvidence(ev: Evidence) {
  selectedEvidence.value = ev
  panelVisible.value = true
  highlightChainId.value = ev.id
}

function handleSelectPerson(pid: string) {
  router.push({
    name: 'PersonPortrait',
    params: {
      caseId: String(caseId.value),
      personId: encodeURIComponent(pid),
    },
  })
}

function handleGraphNodeClick(p: { id: string; kind: EvidenceNodeKind; data: Record<string, unknown> }) {
  highlightChainId.value = p.id
  if (p.kind === 'evidence') {
    const ev = evidenceChainEntries.value.flatMap((e) => e.evidences).find((e) => e.id === p.id)
    if (ev) {
      selectedEvidence.value = ev
      panelVisible.value = true
    }
  }
  if (p.kind === 'action') {
    const el = document.getElementById(`timeline-entry-${p.id}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function handleClosePanel() {
  panelVisible.value = false
}
</script>

<template>
  <div class="evidence-chain-page">
    <StepIndicator :current="4" />

    <div v-if="!hasData" class="empty-state">
      <p>当前案件尚未导入数据</p>
      <p class="empty-hint">请先导入原始数据并完成清洗</p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/import`)">前往数据导入</el-button>
    </div>

    <template v-else>
      <header class="suspect-header">
        <div class="suspect-main">
          <h1 class="suspect-name">{{ personId }}</h1>
          <p class="suspect-case">案件编号: {{ caseStore.currentCase?.case_number || caseId }}</p>
          <div class="suspect-tags">
            <el-tag
              v-for="tag in suspectTags"
              :key="tag"
              :type="tag.includes('异常') || tag.includes('大额') || tag.includes('高频') ? 'danger' : 'info'"
              effect="dark"
              size="default"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
        <div class="suspect-actions">
          <el-button plain :loading="loading" @click="load({ force: true })">刷新数据</el-button>
        </div>
      </header>

      <el-skeleton v-if="loading && !portrait" :rows="10" animated />

      <template v-else-if="portrait">
        <div class="evidence-summary-bar">
          <div class="summary-stat">
            <span class="stat-num">{{ evidenceChainEntries.length }}</span>
            <span class="stat-label">行为记录</span>
          </div>
          <div class="summary-stat">
            <span class="stat-num evidence-highlight">{{ totalEvidenceCount }}</span>
            <span class="stat-label">证据材料</span>
          </div>
          <div class="summary-stat">
            <span class="stat-num confirmed-highlight">{{ confirmedCount }}</span>
            <span class="stat-label">已确认证据</span>
          </div>
          <div class="summary-stat">
            <span class="stat-num">{{ evidenceChainEntries.reduce((s, e) => s + e.relatedPersons.length, 0) }}</span>
            <span class="stat-label">涉及关联人</span>
          </div>
        </div>

        <div class="filter-bar">
          <span class="filter-label">证据筛选</span>
          <el-radio-group v-model="filterType" size="small">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="fund">资金</el-radio-button>
            <el-radio-button value="call">通话</el-radio-button>
            <el-radio-button value="trip">出行</el-radio-button>
          </el-radio-group>
          <el-input
            v-model="filterPerson"
            placeholder="按关联人筛选"
            clearable
            size="small"
            class="filter-person-input"
          />
        </div>

        <div class="dual-panel">
          <div class="panel-left">
            <h2 class="section-title">证据链时间轴</h2>
            <EvidenceTimeline
              :entries="evidenceChainEntries"
              :filter-type="filterType"
              :filter-person="filterPerson"
              @select-evidence="handleSelectEvidence"
              @select-person="handleSelectPerson"
            />
          </div>
          <div class="panel-right" v-if="portraitGraphData && portraitGraphData.nodes.length > 0">
            <h2 class="section-title">证据关系图</h2>
            <div class="portrait-graph-wrap">
              <EvidenceGraph
                :data="portraitGraphData"
                :loading="false"
                :highlight-chain-id="highlightChainId"
                :playback-index="-1"
                filter-type="all"
                @node-click="handleGraphNodeClick"
                @chain-count="() => {}"
              />
            </div>
            <p class="graph-sync-hint">点击图谱节点同步定位到时间轴对应条目</p>
          </div>
        </div>
      </template>

      <el-empty v-else description="暂无数据" />

      <div class="page-footer" v-if="portrait">
        <el-button type="primary" size="large" @click="router.push(`/cases/${caseId}/report`)">
          下一步: 生成证据报告
        </el-button>
      </div>
    </template>

    <EvidencePanel
      :visible="panelVisible"
      :evidence="selectedEvidence"
      @close="handleClosePanel"
    />
  </div>
</template>

<style scoped>
.evidence-chain-page {
  max-width: 1400px;
  margin: 0 auto;
}
.suspect-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  padding: 20px 24px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-card);
}
.suspect-name {
  font-size: 24px;
  font-weight: 700;
  color: var(--app-text);
  margin: 0 0 4px;
}
.suspect-case {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0 0 10px;
  font-family: 'SF Mono', 'Menlo', monospace;
}
.suspect-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.suspect-actions {
  flex-shrink: 0;
}
.evidence-summary-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.summary-stat {
  text-align: center;
  padding: 16px 12px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}
.stat-num {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--app-text);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.evidence-highlight { color: #ca8a04; }
.confirmed-highlight { color: #16a34a; }
.stat-label {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin-top: 2px;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.filter-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-secondary);
}
.filter-person-input {
  width: 200px;
  margin-left: auto;
}
.dual-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}
.panel-left {
  min-width: 0;
}
.panel-right {
  min-width: 0;
}
.portrait-graph-wrap {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  overflow: hidden;
  min-height: 400px;
}
.graph-sync-hint {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin: 6px 0 0;
  text-align: center;
}
.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 16px;
}
.page-footer {
  text-align: center;
  margin-top: 32px;
  padding-bottom: 24px;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 8px; }
.empty-hint { font-size: 13px !important; margin-bottom: 20px !important; }

@media (max-width: 960px) {
  .dual-panel { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .evidence-summary-bar { grid-template-columns: repeat(2, 1fr); }
  .filter-person-input { width: 100%; margin-left: 0; }
}
</style>
