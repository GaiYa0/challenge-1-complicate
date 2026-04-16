<script setup lang="ts">
import { computed } from 'vue'
import type { ClueDetail } from '../../api/clue'
import type { ClueDetailPanelView } from '../../types/clueDetail'
import {
  featureSnapshotToRows,
  formatRiskPromptText,
  formatRuleHitLabel,
  riskLevelTagType,
} from '../../types/clueDetail'

const props = withDefaults(
  defineProps<{
    clueId: number | null
    /** 由 Pinia / 父级拉取后传入 */
    detail: ClueDetail | null
    loading: boolean
    error: string | null
  }>(),
  {
    detail: null,
    loading: false,
    error: null,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'retry'): void
}>()

const view = computed<ClueDetailPanelView>(() => {
  if (props.clueId == null) return 'empty'
  if (props.loading) return 'loading'
  if (props.error) return 'error'
  if (props.detail) return 'ready'
  return 'empty'
})

const featureRows = computed(() => {
  if (!props.detail?.feature_snapshot) return []
  return featureSnapshotToRows(props.detail.feature_snapshot)
})

const ruleHitLabels = computed(() =>
  (props.detail?.rule_hits ?? []).map((h) => formatRuleHitLabel(h)),
)

const riskPromptTexts = computed(() =>
  (props.detail?.risk_prompts ?? [])
    .map((p) => formatRiskPromptText(p))
    .filter((t) => t.length > 0),
)
</script>

<template>
  <aside class="clue-detail-panel" aria-label="线索详情">
    <header class="panel-header">
      <h2 class="panel-title">线索详情</h2>
      <el-button
        v-if="clueId != null"
        text
        type="primary"
        class="panel-close"
        @click="emit('close')"
      >
        关闭
      </el-button>
    </header>

    <div class="panel-body">
      <!-- empty -->
      <div v-if="view === 'empty'" class="state-block state-empty">
        <el-empty description="点击同心圆图中的线索节点查看详情" :image-size="72" />
      </div>

      <!-- loading -->
      <div v-else-if="view === 'loading'" class="state-block state-loading" v-loading="true">
        <div class="loading-placeholder" />
      </div>

      <!-- error -->
      <div v-else-if="view === 'error'" class="state-block state-error">
        <el-result icon="error" title="加载失败" :sub-title="error ?? ''">
          <template #extra>
            <el-button type="primary" @click="emit('retry')">重试</el-button>
          </template>
        </el-result>
      </div>

      <!-- ready -->
      <template v-else-if="view === 'ready' && detail">
        <section class="block block-head">
          <h3 class="detail-title">{{ detail.title }}</h3>
          <div class="meta-row">
            <el-tag :type="riskLevelTagType(detail.risk_level)" effect="dark" round size="small">
              {{ detail.risk_level }}
            </el-tag>
            <span class="score">
              风险分 <strong>{{ detail.risk_score }}</strong>
            </span>
            <span class="category">{{ detail.category }}</span>
          </div>
        </section>

        <section class="block">
          <h4 class="block-label">摘要</h4>
          <p class="summary-text">{{ detail.summary?.trim() || '—' }}</p>
        </section>

        <section class="block">
          <h4 class="block-label">规则命中</h4>
          <div v-if="ruleHitLabels.length" class="tag-list">
            <el-tag
              v-for="(label, i) in ruleHitLabels"
              :key="i"
              type="info"
              effect="plain"
              class="hit-tag"
            >
              {{ label }}
            </el-tag>
          </div>
          <p v-else class="muted">暂无</p>
        </section>

        <section class="block">
          <h4 class="block-label">特征快照</h4>
          <el-table
            v-if="featureRows.length"
            :data="featureRows"
            size="small"
            stripe
            border
            class="feature-table"
            max-height="280"
          >
            <el-table-column prop="key" label="字段" width="120" show-overflow-tooltip />
            <el-table-column prop="value" label="值">
              <template #default="{ row }">
                <pre class="cell-pre">{{ row.value }}</pre>
              </template>
            </el-table-column>
          </el-table>
          <p v-else class="muted">暂无</p>
        </section>

        <section class="block">
          <h4 class="block-label">风险提示</h4>
          <ul v-if="riskPromptTexts.length" class="prompt-list">
            <li v-for="(text, i) in riskPromptTexts" :key="i" class="prompt-item">
              <el-alert type="warning" show-icon :closable="false">
                <span class="prompt-plain">{{ text }}</span>
              </el-alert>
            </li>
          </ul>
          <p v-else class="muted">暂无</p>
        </section>

        <section class="block block-footer-meta">
          <span class="muted">更新 {{ detail.updated_at }}</span>
        </section>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.clue-detail-panel {
  width: 400px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--app-bg-card, #fff);
  border-left: 1px solid var(--app-border, #e5e7eb);
  box-shadow: -4px 0 24px rgba(15, 23, 42, 0.06);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--app-border, #e5e7eb);
  flex-shrink: 0;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text, #0f172a);
}

.panel-close {
  font-size: 13px;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px 20px;
  min-height: 200px;
}

.state-block {
  min-height: 160px;
}

.state-loading {
  position: relative;
}

.loading-placeholder {
  min-height: 200px;
}

.state-error :deep(.el-result) {
  padding: 16px 0;
}

.block {
  margin-bottom: 20px;
}

.block:last-child {
  margin-bottom: 0;
}

.block-head .detail-title {
  margin: 0 0 10px;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--app-text, #0f172a);
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  font-size: 13px;
  color: var(--app-text-secondary, #64748b);
}

.meta-row .score strong {
  color: var(--app-text, #0f172a);
  font-variant-numeric: tabular-nums;
}

.block-label {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--app-text-secondary, #64748b);
}

.summary-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--app-text, #334155);
  white-space: pre-wrap;
  word-break: break-word;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hit-tag {
  max-width: 100%;
}

.feature-table {
  width: 100%;
}

.cell-pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, monospace;
}

.prompt-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.prompt-item + .prompt-item {
  margin-top: 8px;
}

.prompt-plain {
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.block-footer-meta {
  padding-top: 8px;
  border-top: 1px dashed var(--app-border, #e5e7eb);
}

.muted {
  margin: 0;
  font-size: 13px;
  color: var(--app-text-secondary, #94a3b8);
}
</style>
