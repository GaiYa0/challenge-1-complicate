<script setup lang="ts">
/**
 * 人物画像列表 — 展示当前案件关系网络中的所有人物，点击进入详细画像。
 */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { useCaseStore } from '../store/case'
import { useFileStore } from '../store/modules/file.store'
import { useRelationshipAnalysisStore } from '../store/relationshipAnalysis'
import StepIndicator from '../components/investigation/StepIndicator.vue'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const fileStore = useFileStore()
const rel = useRelationshipAnalysisStore()

const caseId = computed(() => Number(route.params.caseId))
const hasData = computed(() => fileStore.items.length > 0)

interface PersonEntry {
  id: string
  label: string
  degree: number
}

const persons = computed<PersonEntry[]>(() => {
  if (!rel.graphData || !rel.graphData.nodes.length) return []
  const degreeMap = new Map<string, number>()
  for (const d of rel.degreeList) {
    degreeMap.set(d.name, d.degree)
  }
  return rel.graphData.nodes.map((n) => ({
    id: n.id,
    label: n.label ?? n.id,
    degree: degreeMap.get(n.label ?? n.id) ?? 0,
  })).sort((a, b) => b.degree - a.degree)
})

watch(
  caseId,
  async (id) => {
    if (!Number.isFinite(id) || id <= 0) return
    caseStore.selectCase(id)
    rel.bindCase(id)
    await fileStore.fetchList(`case-${id}`)
    if (hasData.value) {
      void rel.loadMainGraph()
    }
  },
  { immediate: true },
)

function goPortrait(person: PersonEntry) {
  router.push({
    name: 'PersonPortrait',
    params: {
      caseId: String(caseId.value),
      personId: encodeURIComponent(person.label),
    },
  })
}
</script>

<template>
  <div class="portrait-list-page">
    <StepIndicator :current="4" />

    <h1 class="page-title">证据链分析</h1>
    <p class="page-subtitle">选择嫌疑人或关联人查看完整证据链，包括行为记录、证据材料和关联人影响</p>

    <div v-if="!hasData" class="empty-state">
      <p>当前案件尚未导入数据</p>
      <p class="empty-hint">请先导入原始数据并完成清洗</p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/import`)">前往数据导入</el-button>
    </div>

    <div v-else-if="rel.mainLoading && !rel.graphData" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="persons.length === 0" class="empty-state">
      <p>暂无人物数据</p>
      <p class="empty-hint">
        人物列表来自本案表格文件（CSV / XLS / XLSX）构图中的本方与对手列；请确认已上传含可解析列的流水，或前往证据关系图查看是否已解析出边。
      </p>
      <el-button type="primary" @click="router.push(`/cases/${caseId}/import`)">前往数据导入</el-button>
    </div>

    <div v-else class="person-grid">
      <div
        v-for="p in persons"
        :key="p.id"
        class="person-card"
        @click="goPortrait(p)"
      >
        <div class="person-avatar">{{ p.label.charAt(0) }}</div>
        <div class="person-info">
          <div class="person-name">{{ p.label }}</div>
          <div class="person-meta">
            <span v-if="p.degree > 0">关联次数: {{ p.degree }}</span>
            <span v-else>暂无关联记录</span>
          </div>
        </div>
        <el-icon class="person-arrow"><ArrowRight /></el-icon>
      </div>
    </div>

    <div class="page-footer" v-if="persons.length > 0">
      <el-button type="primary" size="large" @click="router.push(`/cases/${caseId}/report`)">
        下一步: 证据报告
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.portrait-list-page { max-width: 900px; margin: 0 auto; }
.page-title {
  font-size: 22px; font-weight: 700; color: var(--app-text);
  margin: 0 0 4px; text-align: center;
}
.page-subtitle {
  font-size: 14px; color: var(--app-text-secondary);
  text-align: center; margin: 0 0 28px;
  max-width: 560px; margin-left: auto; margin-right: auto;
  line-height: 1.6;
}
.person-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}
.person-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  cursor: pointer;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.person-card:hover {
  border-color: var(--app-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.person-avatar {
  width: 42px; height: 42px;
  border-radius: 50%;
  background: var(--app-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
}
.person-info { flex: 1; min-width: 0; }
.person-name {
  font-size: 15px; font-weight: 600;
  color: var(--app-text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.person-meta {
  font-size: 13px; color: var(--app-text-secondary);
  margin-top: 2px;
}
.person-arrow {
  color: var(--app-text-secondary);
  font-size: 16px;
  flex-shrink: 0;
}
.empty-state { text-align: center; padding: 60px 0; }
.empty-state p { font-size: 16px; color: var(--app-text-secondary); margin-bottom: 8px; }
.empty-hint { font-size: 13px !important; margin-bottom: 20px !important; }
.loading-state { padding: 40px 0; }
.page-footer { text-align: center; margin-top: 28px; padding-bottom: 20px; }
</style>
