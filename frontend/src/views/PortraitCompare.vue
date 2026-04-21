<script setup lang="ts">
/**
 * 人物画像对比页：URL `?ids=a,b`。
 * 单列：只显示一个；双列：两人并排，差异项高亮。
 */
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getPersonPortrait, type PersonPortrait } from '../api/portrait'
import { notifyError } from '../utils/notify'
import CountUp from '../components/common/CountUp.vue'
import FormatAmount from '../components/common/FormatAmount.vue'
import StatusTag from '../components/common/StatusTag.vue'
import { useCaseStore } from '../store/case'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()

const caseId = computed(() => Number(route.params.caseId))

interface Slot {
  personId: string
  loading: boolean
  error: string | null
  data: PersonPortrait | null
}

function emptySlot(): Slot {
  return { personId: '', loading: false, error: null, data: null }
}

const left = ref<Slot>(emptySlot())
const right = ref<Slot>(emptySlot())

const leftInput = ref('')
const rightInput = ref('')

function parseIds(): string[] {
  const raw = String(route.query.ids ?? '')
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 2)
}

async function loadSlot(slot: Slot, personId: string): Promise<void> {
  if (!personId) {
    Object.assign(slot, emptySlot())
    return
  }
  slot.personId = personId
  slot.loading = true
  slot.error = null
  try {
    const data = await getPersonPortrait(caseId.value, personId)
    slot.data = data ?? null
    if (!data) slot.error = '未获得画像数据'
  } catch (e) {
    slot.error = e instanceof Error ? e.message : String(e)
    slot.data = null
    notifyError(slot.error || '加载失败')
  } finally {
    slot.loading = false
  }
}

function applyIdsFromQuery() {
  const [a, b] = parseIds()
  leftInput.value = a ?? ''
  rightInput.value = b ?? ''
  void loadSlot(left.value, a ?? '')
  void loadSlot(right.value, b ?? '')
}

function syncQuery() {
  const ids = [leftInput.value, rightInput.value].map((v) => v.trim()).filter(Boolean)
  router.replace({
    path: route.path,
    query: ids.length ? { ids: ids.join(',') } : {},
  })
}

function handleLoadLeft() {
  syncQuery()
  void loadSlot(left.value, leftInput.value.trim())
}
function handleLoadRight() {
  syncQuery()
  void loadSlot(right.value, rightInput.value.trim())
}
function handleSwap() {
  const tmp = leftInput.value
  leftInput.value = rightInput.value
  rightInput.value = tmp
  syncQuery()
  void loadSlot(left.value, leftInput.value)
  void loadSlot(right.value, rightInput.value)
}

onMounted(() => {
  caseStore.selectCase(caseId.value)
  applyIdsFromQuery()
})
watch(() => route.query.ids, () => applyIdsFromQuery())

/** 差异判定：两侧都有数据时，对关键指标进行高亮 */
function diffClass(path: 'risk_score' | 'total_amount' | 'anomaly_ratio' | 'transfer_out_count' | 'transfer_in_count'): string {
  const a = left.value.data
  const b = right.value.data
  if (!a || !b) return ''
  const pick = (d: PersonPortrait) => {
    switch (path) {
      case 'risk_score': return d.basic_info.risk_score
      case 'total_amount': return d.economic.total_amount
      case 'anomaly_ratio': return d.economic.anomaly_ratio
      case 'transfer_out_count': return d.economic.transfer_out_count
      case 'transfer_in_count': return d.economic.transfer_in_count
    }
  }
  const va = pick(a)
  const vb = pick(b)
  if (va === vb) return ''
  return 'diff-cell'
}

const hasBoth = computed(() => Boolean(left.value.data && right.value.data))
</script>

<template>
  <div class="compare-page">
    <header class="page-head">
      <h1 class="page-title">人物画像对比</h1>
      <p class="page-subtitle">输入两个对象 ID，系统将并排呈现关键画像指标并高亮差异项。</p>
    </header>

    <div class="compare-controls">
      <el-input
        v-model="leftInput"
        placeholder="左侧对象 ID"
        clearable
        class="compare-input"
        @keyup.enter="handleLoadLeft"
      >
        <template #prepend>A</template>
      </el-input>
      <el-button @click="handleSwap" :disabled="!leftInput && !rightInput">互换</el-button>
      <el-input
        v-model="rightInput"
        placeholder="右侧对象 ID"
        clearable
        class="compare-input"
        @keyup.enter="handleLoadRight"
      >
        <template #prepend>B</template>
      </el-input>
      <el-button type="primary" @click="() => { handleLoadLeft(); handleLoadRight() }">对比</el-button>
    </div>

    <div class="compare-grid">
      <section
        v-for="(slot, key) in [{ s: left, key: 'L' }, { s: right, key: 'R' }]"
        :key="key"
        class="compare-col"
      >
        <template v-if="slot.s.loading">
          <el-skeleton :rows="10" animated />
        </template>
        <template v-else-if="!slot.s.personId">
          <div class="slot-empty">
            <p>输入 ID 后点击「对比」以加载</p>
          </div>
        </template>
        <template v-else-if="slot.s.error && !slot.s.data">
          <el-empty :description="slot.s.error" />
        </template>
        <template v-else-if="slot.s.data">
          <header class="slot-head">
            <h2 class="slot-name">{{ slot.s.data.basic_info.display_name || slot.s.personId }}</h2>
            <StatusTag :raw="slot.s.data.basic_info.risk_level" />
          </header>

          <dl class="slot-body">
            <div class="slot-row" :class="diffClass('risk_score')">
              <dt>风险分</dt>
              <dd><CountUp :value="slot.s.data.basic_info.risk_score" :fraction-digits="0" /> / 100</dd>
            </div>
            <div class="slot-row">
              <dt>概述</dt>
              <dd class="slot-summary">{{ slot.s.data.basic_info.summary }}</dd>
            </div>
            <div class="slot-row" :class="diffClass('total_amount')">
              <dt>资金往来总额</dt>
              <dd><FormatAmount :value="slot.s.data.economic.total_amount" compact animated /></dd>
            </div>
            <div class="slot-row" :class="diffClass('anomaly_ratio')">
              <dt>异常占比</dt>
              <dd>{{ (slot.s.data.economic.anomaly_ratio * 100).toFixed(1) }}%</dd>
            </div>
            <div class="slot-row" :class="diffClass('transfer_out_count')">
              <dt>对外转账次数</dt>
              <dd><CountUp :value="slot.s.data.economic.transfer_out_count" :fraction-digits="0" /></dd>
            </div>
            <div class="slot-row" :class="diffClass('transfer_in_count')">
              <dt>资金流入次数</dt>
              <dd><CountUp :value="slot.s.data.economic.transfer_in_count" :fraction-digits="0" /></dd>
            </div>
            <div class="slot-row">
              <dt>活动轨迹</dt>
              <dd>
                共 {{ slot.s.data.behavior.timeline_bins.length }} 个时间段 ·
                {{ slot.s.data.behavior.map_points.length }} 个位置点
              </dd>
            </div>
            <div class="slot-row">
              <dt>社会关系</dt>
              <dd>
                节点 {{ slot.s.data.social.graph.nodes.length }} · 边
                {{ slot.s.data.social.graph.edges.length }}
              </dd>
            </div>
            <div class="slot-row">
              <dt>相关线索</dt>
              <dd>{{ slot.s.data.clues.length }} 条</dd>
            </div>
          </dl>

          <footer class="slot-foot">
            <el-button
              text
              @click="router.push({ path: `/cases/${caseId}/persons/${encodeURIComponent(slot.s.personId)}/portrait` })"
            >
              查看完整画像 &rarr;
            </el-button>
          </footer>
        </template>
      </section>
    </div>

    <p v-if="hasBoth" class="compare-hint">高亮行表示两侧存在差异。</p>
  </div>
</template>

<style scoped>
.compare-page {
  max-width: 1400px;
  margin: 0 auto;
}
.page-head {
  margin-bottom: 16px;
}
.page-title {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--app-text);
}
.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--app-text-secondary);
}
.compare-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}
.compare-input {
  width: 260px;
}
.compare-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 860px) {
  .compare-grid { grid-template-columns: 1fr; }
  .compare-input { width: 100%; }
}
.compare-col {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 20px;
  box-shadow: var(--app-shadow-card);
  min-height: 400px;
}
.slot-empty {
  color: var(--app-text-secondary);
  text-align: center;
  padding: 80px 0;
}
.slot-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--app-border);
  margin-bottom: 12px;
}
.slot-name {
  margin: 0;
  font-size: 18px;
  color: var(--app-text);
  font-weight: 700;
}
.slot-body { margin: 0; }
.slot-row {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 6px;
  font-size: 14px;
  transition: background 0.18s ease;
}
.slot-row dt {
  color: var(--app-text-secondary);
  margin: 0;
}
.slot-row dd {
  color: var(--app-text);
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.slot-row.diff-cell {
  background: var(--app-warning-light);
}
html.dark .slot-row.diff-cell {
  background: rgba(250, 173, 20, 0.12);
}
.slot-summary {
  line-height: 1.6;
  color: var(--app-text-secondary);
}
.slot-foot {
  margin-top: 14px;
  text-align: right;
}
.compare-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--app-text-secondary);
  text-align: right;
}
</style>
