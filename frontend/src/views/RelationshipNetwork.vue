<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, VideoPlay, VideoPause, RefreshRight, Download, User, Link } from '@element-plus/icons-vue'
import { useCaseStore } from '../store/case'
import { useFileStore } from '../store/modules/file.store'
import { useRelationshipAnalysisStore } from '../store/relationshipAnalysis'
import { getMergedCasesGraph } from '../api/graph'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import EvidenceGraph from '../components/evidence/EvidenceGraph.vue'
import EvidenceFilterPanel from '../components/evidence/EvidenceFilterPanel.vue'
import EvidencePanel from '../components/evidence/EvidencePanel.vue'
import type {
  EvidenceGraphData, EvidenceGraphNode, EvidenceGraphEdge,
  EvidenceNodeKind, Evidence, ActionType,
} from '../types/evidence'
import { ACTION_TYPE_LABELS } from '../types/evidence'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const fileStore = useFileStore()
const rel = useRelationshipAnalysisStore()

const caseId = computed(() => Number(route.params.caseId))
const hasData = computed(() => fileStore.items.length > 0)

const keyword = ref('')
const highlightChainId = ref<string | null>(null)
const panelVisible = ref(false)
const selectedEvidence = ref<Evidence | null>(null)
const filterType = ref<ActionType | 'all'>('all')
const selectedPersonId = ref<string | null>(null)
const selectedSuspectId = ref<string | null>(null)
const linkedCaseIds = ref<number[]>([])
const mergedGraphMode = ref(false)
const mergedLoading = ref(false)
const isPlaying = ref(false)
const playbackIndex = ref(-1)
const chainCount = ref(0)
let playTimer: ReturnType<typeof setInterval> | null = null
const mergedGraphOverride = ref<EvidenceGraphData | null>(null)

function stopPlay() { isPlaying.value = false; if (playTimer) { clearInterval(playTimer); playTimer = null } }
function resetPlay() { stopPlay(); playbackIndex.value = -1 }
function resetFilters() { filterType.value = 'all'; selectedPersonId.value = null; keyword.value = ''; highlightChainId.value = null; resetPlay() }

const suspectCandidates = computed(() => {
  if (!rel.graphData) return []
  return rel.graphData.nodes.map((n) => ({ id: n.id, name: n.label ?? n.id }))
})

const activeSuspectId = computed(() => {
  if (!rel.graphData || !rel.graphData.nodes.length) return null
  if (selectedSuspectId.value) {
    const exists = rel.graphData.nodes.find((n) => n.id === selectedSuspectId.value)
    if (exists) return selectedSuspectId.value
  }
  return rel.graphData.nodes[0].id
})

const evidenceGraphData = computed<EvidenceGraphData | null>(() => {
  if (!rel.graphData || !rel.graphData.nodes.length) return null
  const suspectId = activeSuspectId.value
  if (!suspectId) return null

  const nodes: EvidenceGraphNode[] = []
  const edges: EvidenceGraphEdge[] = []
  const kw = keyword.value.trim().toLowerCase()
  const allNodes = rel.graphData.nodes
  const allEdges = rel.graphData.edges

  const suspectNode = allNodes.find((n) => n.id === suspectId)
  if (!suspectNode) return null
  nodes.push({ id: suspectId, kind: 'suspect', label: suspectNode.label ?? suspectId })

  const relatedEdges = allEdges.filter((e) => e.source === suspectId || e.target === suspectId)

  let ac = 0
  const at: ActionType = 'fund'

  for (const edge of relatedEdges) {
    const from = allNodes.find((n) => n.id === edge.source)
    const to = allNodes.find((n) => n.id === edge.target)
    if (!from || !to) continue
    if (kw) {
      const fl = (from.label ?? '').toLowerCase()
      const tl = (to.label ?? '').toLowerCase()
      if (!fl.includes(kw) && !tl.includes(kw)) continue
    }
    if (selectedPersonId.value) {
      const pid = edge.target === suspectId ? edge.source : edge.target
      if (pid !== selectedPersonId.value) continue
    }
    const aId = `action-${ac}`
    const eId = `evidence-${ac}`
    const w = typeof edge.weight === 'number' && Number.isFinite(edge.weight) ? edge.weight : undefined
    ac++

    const baseEv = `${from.label ?? edge.source} → ${to.label ?? edge.target}`
    const evLabel =
      w != null ? `${baseEv} · ${w.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}元` : baseEv

    nodes.push({
      id: aId,
      kind: 'action',
      label: ACTION_TYPE_LABELS[at],
      data: { actionType: at, time: `2024-01-${String(ac).padStart(2, '0')}`, amount: w },
    })
    nodes.push({
      id: eId,
      kind: 'evidence',
      label: evLabel,
      data: {
        sourceLabel: from.label,
        targetLabel: to.label,
        actionType: at,
        amount: w,
      },
    })
    edges.push({ id: `e-s-${aId}`, source: suspectId, target: aId, label: '', actionType: at })
    edges.push({
      id: `e-a-${aId}`,
      source: aId,
      target: eId,
      label: w != null ? `${w.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}元` : '产生证据',
      actionType: at,
      weight: w,
    })
  }
  return { nodes, edges }
})

const activeGraphData = computed(() => {
  if (mergedGraphMode.value && mergedGraphOverride.value) return mergedGraphOverride.value
  return evidenceGraphData.value
})

const nodeStats = computed(() => {
  if (!activeGraphData.value) return { suspect: 0, action: 0, evidence: 0 }
  const c = { suspect: 0, action: 0, evidence: 0 }
  for (const n of activeGraphData.value.nodes) { if (n.kind in c) c[n.kind as keyof typeof c]++ }
  return c
})

const personList = computed(() => {
  if (!rel.graphData) return []
  return rel.graphData.nodes
    .filter((n) => n.id !== activeSuspectId.value)
    .map((n) => ({ id: n.id, name: n.label ?? n.id }))
})

watch(caseId, async (id) => {
  if (!Number.isFinite(id) || id <= 0) return
  caseStore.selectCase(id)
  mergedGraphMode.value = false
  mergedGraphOverride.value = null
  linkedCaseIds.value = []
  resetFilters()
  if (caseStore.cases.length === 0) void caseStore.fetchCases()
  await fileStore.fetchList(`case-${id}`)
  rel.bindCase(id)
  if (hasData.value) { void rel.loadMainGraph() }
}, { immediate: true })

function handleNodeClick(p: { id: string; kind: EvidenceNodeKind; data: Record<string, unknown> }) {
  if (p.kind === 'action') {
    highlightChainId.value = p.id
  } else if (p.kind === 'evidence') {
    highlightChainId.value = p.id
    selectedEvidence.value = {
      id: p.id, actionId: '', source: String(p.data.sourceLabel ?? ''),
      sourceType: String(p.data.actionType ?? 'fund'), recordId: p.id,
      ruleHit: '关系网络分析命中',
      rawContent: `来源: ${p.data.sourceLabel ?? ''}\n目标: ${p.data.targetLabel ?? ''}`,
      remark: '', status: 'pending', time: new Date().toISOString().slice(0, 10),
    }
    panelVisible.value = true
  } else if (p.kind === 'person') {
    router.push({ name: 'PersonPortrait', params: { caseId: String(caseId.value), personId: encodeURIComponent(String(p.data.label ?? p.id)) } })
  }
}

function handleChainCount(count: number) { chainCount.value = count }

function togglePlay() { isPlaying.value ? stopPlay() : startPlay() }
function startPlay() {
  isPlaying.value = true; playbackIndex.value = 0
  playTimer = setInterval(() => { if (playbackIndex.value >= chainCount.value) { stopPlay(); return }; playbackIndex.value++ }, 1200)
}

function onSuspectChange(id: string) {
  selectedSuspectId.value = id
  selectedPersonId.value = null
  highlightChainId.value = null
  resetPlay()
}

const otherCases = computed(() =>
  caseStore.cases.filter((c) => c.id !== caseId.value),
)

async function loadMergedGraph() {
  if (linkedCaseIds.value.length === 0) {
    mergedGraphMode.value = false
    return
  }
  mergedLoading.value = true
  mergedGraphMode.value = true
  try {
    const allIds = [caseId.value, ...linkedCaseIds.value]
    const merged = await getMergedCasesGraph(allIds)
    const nodes: EvidenceGraphNode[] = []
    const edges: EvidenceGraphEdge[] = []
    const suspectId = merged.nodes[0]?.id as string
    if (!suspectId) return

    nodes.push({ id: suspectId, kind: 'suspect', label: String(merged.nodes[0].label ?? suspectId) })
    let ac = 0
    const mat: ActionType = 'fund'
    for (const e of merged.edges) {
      const src = String(e.source ?? '')
      const tgt = String(e.target ?? '')
      if (!src || !tgt) continue
      const aId = `merged-action-${ac}`
      const eId = `merged-evidence-${ac}`
      const mw =
        typeof (e as { weight?: unknown }).weight === 'number' &&
        Number.isFinite((e as { weight: number }).weight)
          ? (e as { weight: number }).weight
          : undefined
      ac++
      const baseM = `${src} → ${tgt}`
      const mEvLabel =
        mw != null ? `${baseM} · ${mw.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}元` : baseM
      nodes.push({
        id: aId,
        kind: 'action',
        label: ACTION_TYPE_LABELS[mat],
        data: { actionType: mat, case_id: e.case_id, time: `2024-01-${String(ac).padStart(2, '0')}`, amount: mw },
      })
      nodes.push({
        id: eId,
        kind: 'evidence',
        label: mEvLabel,
        data: { sourceLabel: src, targetLabel: tgt, actionType: mat, case_id: e.case_id, amount: mw },
      })
      edges.push({ id: `me-s-${aId}`, source: suspectId, target: aId, label: '', actionType: mat })
      edges.push({
        id: `me-a-${aId}`,
        source: aId,
        target: eId,
        label: mw != null ? `${mw.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}元` : '产生证据',
        actionType: mat,
        weight: mw,
      })
    }
    mergedGraphOverride.value = { nodes, edges }
  } catch {
    mergedGraphMode.value = false
  } finally {
    mergedLoading.value = false
  }
}

function clearMergedGraph() {
  linkedCaseIds.value = []
  mergedGraphMode.value = false
  mergedGraphOverride.value = null
}

async function exportImage() {
  const canvas = document.querySelector('.canvas canvas') as HTMLCanvasElement | null
  if (!canvas) return
  try {
    const url = canvas.toDataURL('image/png')
    const a = document.createElement('a'); a.download = `证据链_${caseId.value}_${Date.now()}.png`; a.href = url; a.click()
  } catch { const { ElMessage } = await import('element-plus'); ElMessage.warning('导出失败，请截图保存') }
}

function goNext() { router.push(`/cases/${caseId.value}/portraits`) }
</script>

<template>
  <div class="network-page">
    <StepIndicator :current="3" />
    <div class="page-header">
      <h1 class="page-title">证据关系图</h1>
      <p class="page-subtitle">径向分层布局 — 嫌疑人(中心) / 行为(内环) / 证据(外环)</p>
    </div>

    <div v-if="!hasData" class="empty-state">
      <div class="empty-icon"><svg width="64" height="64" viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="30" stroke="#e5e7eb" stroke-width="2"/><path d="M22 32h20M32 22v20" stroke="#d1d5db" stroke-width="2" stroke-linecap="round"/></svg></div>
      <p class="empty-text">当前案件尚未导入数据</p>
      <p class="empty-hint">请先导入原始数据并完成清洗，证据关系图基于清洗结果生成</p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/import`)">前往数据导入</el-button>
    </div>

    <div v-else-if="rel.mainLoading && !rel.graphData" class="loading-state"><el-skeleton :rows="6" animated /></div>

    <div v-else-if="rel.graphError" class="error-state">
      <el-result icon="error" title="证据关系图加载失败" :sub-title="rel.graphError">
        <template #extra><el-button type="primary" @click="rel.loadMainGraph()">重试</el-button></template>
      </el-result>
    </div>

    <template v-else-if="activeGraphData && activeGraphData.nodes.length > 0">
      <div class="suspect-selector">
        <div class="ss-label">
          <el-icon class="ss-icon"><User /></el-icon>
          <span>选择中心嫌疑人</span>
        </div>
        <div class="ss-chips">
          <button
            v-for="c in suspectCandidates"
            :key="c.id"
            :class="['ss-chip', { 'ss-chip--active': activeSuspectId === c.id }]"
            @click="onSuspectChange(c.id)"
          >
            {{ c.name }}
          </button>
        </div>
      </div>

      <div v-if="otherCases.length > 0" class="cross-case-bar">
        <div class="cc-label">
          <el-icon class="cc-icon"><Link /></el-icon>
          <span>关联案件</span>
        </div>
        <el-select
          v-model="linkedCaseIds"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择要合并图谱的案件"
          class="cc-select"
          size="default"
          @change="loadMergedGraph"
        >
          <el-option
            v-for="c in otherCases"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          />
        </el-select>
        <el-button v-if="mergedGraphMode" text size="small" @click="clearMergedGraph">清除合并</el-button>
        <span v-if="mergedGraphMode" class="cc-hint">当前为多案件合并视图</span>
      </div>

      <div class="stats-row">
        <div class="stat-card stat-card--suspect"><span class="stat-value">{{ nodeStats.suspect }}</span><span class="stat-label">嫌疑人</span></div>
        <div class="stat-card stat-card--action"><span class="stat-value">{{ nodeStats.action }}</span><span class="stat-label">行为记录</span></div>
        <div class="stat-card stat-card--evidence"><span class="stat-value">{{ nodeStats.evidence }}</span><span class="stat-label">证据材料</span></div>
      </div>

      <EvidenceFilterPanel :active-type="filterType" :person-list="personList" :selected-person-id="selectedPersonId"
        @update:active-type="filterType = $event" @update:selected-person-id="selectedPersonId = $event" @reset="resetFilters" />

      <div class="graph-toolbar">
        <el-input v-model="keyword" placeholder="搜索关键词" clearable class="toolbar-search" size="default">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="toolbar-divider" />
        <div class="playback-controls">
          <el-button :icon="isPlaying ? VideoPause : VideoPlay" :type="isPlaying ? 'danger' : 'primary'" size="small" @click="togglePlay">{{ isPlaying ? '暂停' : '播放证据链' }}</el-button>
          <el-button :icon="RefreshRight" size="small" @click="resetPlay" :disabled="playbackIndex < 0">重置</el-button>
          <span v-if="playbackIndex >= 0" class="playback-progress">{{ playbackIndex }} / {{ chainCount }}</span>
        </div>
        <div class="toolbar-divider" />
        <el-button :icon="Download" text size="small" @click="exportImage">导出图片</el-button>
        <el-button text size="small" @click="resetFilters">全部重置</el-button>
      </div>

      <div class="graph-container">
        <EvidenceGraph :data="activeGraphData" :loading="rel.mainLoading || mergedLoading" :highlight-chain-id="highlightChainId"
          :playback-index="playbackIndex" :filter-type="filterType"
          @node-click="handleNodeClick" @chain-count="handleChainCount" />
      </div>
      <p class="graph-hint">点击行为节点高亮所属簇 | 点击证据节点查看详情 | 滚轮缩放、拖拽平移</p>
    </template>

    <div v-else class="empty-state">
      <p class="empty-text">当前案件暂无可用关系边</p>
      <p class="empty-hint">
        请上传资金类 CSV，且包含 <strong>name</strong>（户名）与 <strong>counterparty</strong>（对手方）列；仅本案 dataset 下的文件会参与构图。
      </p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/import`)">前往数据导入</el-button>
    </div>

    <div class="page-footer" v-if="activeGraphData && activeGraphData.nodes.length > 0">
      <el-button type="primary" size="large" @click="goNext">下一步: 查看证据链</el-button>
    </div>
    <EvidencePanel :visible="panelVisible" :evidence="selectedEvidence" @close="panelVisible = false" />
  </div>
</template>

<style scoped>
.network-page { max-width: 1400px; margin: 0 auto; padding-bottom: 40px; }
.page-header { text-align: center; margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; color: var(--app-text); margin: 0 0 4px; }
.page-subtitle { font-size: 14px; color: var(--app-text-secondary); margin: 0; }

.suspect-selector {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 18px;
  margin-bottom: 14px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-card);
}
.ss-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  white-space: nowrap;
  padding-top: 4px;
}
.ss-icon { color: #dc2626; font-size: 16px; }
.ss-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ss-chip {
  padding: 5px 16px;
  border-radius: 18px;
  border: 1.5px solid var(--app-border);
  background: transparent;
  font-size: 13px;
  color: var(--app-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.ss-chip:hover {
  border-color: #dc2626;
  color: #dc2626;
}
.ss-chip--active {
  background: #dc2626;
  border-color: #dc2626;
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(220, 38, 38, 0.25);
}

.cross-case-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  margin-bottom: 12px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-card);
  flex-wrap: wrap;
}
.cc-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  white-space: nowrap;
}
.cc-icon { color: #2563eb; font-size: 16px; }
.cc-select { width: 320px; }
.cc-hint { font-size: 12px; color: #ca8a04; font-weight: 500; }

.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { text-align: center; padding: 16px 12px; background: var(--app-bg-card); border: 1px solid var(--app-border); border-radius: var(--app-radius); box-shadow: var(--app-shadow-card); }
.stat-card--suspect { border-left: 4px solid #dc2626; }
.stat-card--action { border-left: 4px solid #2563eb; }
.stat-card--evidence { border-left: 4px solid #ca8a04; }
.stat-value { display: block; font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.2; }
.stat-card--suspect .stat-value { color: #dc2626; }
.stat-card--action .stat-value { color: #2563eb; }
.stat-card--evidence .stat-value { color: #ca8a04; }
.stat-label { font-size: 12px; color: var(--app-text-secondary); margin-top: 2px; }

.graph-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 10px 16px; background: var(--app-bg-card); border: 1px solid var(--app-border); border-radius: var(--app-radius); flex-wrap: wrap; }
.toolbar-search { width: 240px; }
.toolbar-divider { width: 1px; height: 24px; background: var(--app-border); flex-shrink: 0; }
.playback-controls { display: flex; align-items: center; gap: 8px; }
.playback-progress { font-size: 12px; font-weight: 600; color: var(--app-primary); font-variant-numeric: tabular-nums; }

.graph-container { background: var(--app-bg-card); border: 1px solid var(--app-border); border-radius: var(--app-radius); padding: 0; margin-bottom: 8px; overflow: hidden; }
.graph-hint { font-size: 12px; color: var(--app-text-secondary); margin: 0 0 24px; text-align: center; }

.empty-state { text-align: center; padding: 80px 0 60px; }
.empty-icon { margin-bottom: 16px; }
.empty-text { font-size: 16px; color: var(--app-text); margin-bottom: 8px; font-weight: 500; }
.empty-hint { font-size: 13px; color: var(--app-text-secondary); margin-bottom: 20px; }
.loading-state { padding: 40px 0; }
.error-state { padding: 32px 0; }
.page-footer { text-align: center; margin-top: 24px; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
