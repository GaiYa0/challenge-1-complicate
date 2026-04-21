<script setup lang="ts">
defineOptions({ name: 'CaseList' })
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { useCaseStore } from '../store/case'
import CaseCard from '../components/investigation/CaseCard.vue'
import { notifySuccess, notifyError } from '../utils/notify'
import { ElMessageBox } from 'element-plus'
import { isMessageBoxDismiss } from '../utils/elMessageBox'

type StatusFilter = 'all' | 'active' | 'completed'
type SortBy = 'created_desc' | 'created_asc' | 'name_asc' | 'name_desc'

const router = useRouter()
const caseStore = useCaseStore()

const showCreate = ref(false)
const createForm = ref({ name: '', case_number: '', note: '' })
const creating = ref(false)

const keyword = ref('')
const statusFilter = ref<StatusFilter>('all')
const sortBy = ref<SortBy>('created_desc')

onMounted(() => {
  void caseStore.fetchCases(1)
})

const filteredCases = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const statusKey = statusFilter.value
  const result = caseStore.cases.filter((c) => {
    if (statusKey !== 'all' && (c.status ?? '').toLowerCase() !== statusKey) return false
    if (!kw) return true
    const haystack = [c.name, c.case_number ?? '', c.note ?? ''].join(' ').toLowerCase()
    return haystack.includes(kw)
  })
  return result.sort((a, b) => {
    switch (sortBy.value) {
      case 'created_asc':
        return String(a.created_at).localeCompare(String(b.created_at))
      case 'name_asc':
        return String(a.name).localeCompare(String(b.name), 'zh-Hans-CN')
      case 'name_desc':
        return String(b.name).localeCompare(String(a.name), 'zh-Hans-CN')
      case 'created_desc':
      default:
        return String(b.created_at).localeCompare(String(a.created_at))
    }
  })
})

const isEmptyAfterFilter = computed(() =>
  caseStore.cases.length > 0 && filteredCases.value.length === 0,
)

function resetFilters() {
  keyword.value = ''
  statusFilter.value = 'all'
  sortBy.value = 'created_desc'
}

async function handleCreate() {
  if (!createForm.value.name.trim()) return
  creating.value = true
  try {
    const c = await caseStore.addCase({
      name: createForm.value.name.trim(),
      case_number: createForm.value.case_number.trim() || undefined,
      note: createForm.value.note.trim() || undefined,
    })
    showCreate.value = false
    createForm.value = { name: '', case_number: '', note: '' }
    notifySuccess('案件创建成功')
    router.push(`/cases/${c.id}/import`)
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该案件？删除后无法恢复。', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await caseStore.removeCase(id)
    notifySuccess('已删除')
  } catch (e) {
    if (!isMessageBoxDismiss(e)) notifyError('删除失败')
  }
}

async function handleRename(id: number) {
  const c = caseStore.cases.find((x) => x.id === id)
  if (!c) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新案件名称', '重命名案件', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputValue: c.name,
      inputValidator: (v: string) => (v.trim().length > 0 ? true : '名称不能为空'),
    })
    if (value && value.trim() !== c.name) {
      await caseStore.renameCase(id, value.trim())
      notifySuccess('重命名成功')
    }
  } catch (e) {
    if (!isMessageBoxDismiss(e)) notifyError('重命名失败')
  }
}

function handleEnter(id: number) {
  caseStore.selectCase(id)
  router.push(`/cases/${id}/import`)
}
</script>

<template>
  <div class="case-list-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">案件管理</h1>
        <p class="page-subtitle">选择已有案件继续调查，或创建新案件。所有分析基于数据清洗结果。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" @click="showCreate = true">新建案件</el-button>
      </div>
    </div>

    <div class="toolbar" v-if="caseStore.cases.length > 0 || caseStore.loading">
      <el-input
        v-model="keyword"
        placeholder="搜索案件名称 / 编号 / 备注"
        clearable
        size="default"
        class="toolbar-search"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="statusFilter" size="default" class="toolbar-status">
        <el-option label="全部状态" value="all" />
        <el-option label="进行中" value="active" />
        <el-option label="已完成" value="completed" />
      </el-select>
      <el-select v-model="sortBy" size="default" class="toolbar-sort">
        <el-option label="最新创建" value="created_desc" />
        <el-option label="最早创建" value="created_asc" />
        <el-option label="名称升序" value="name_asc" />
        <el-option label="名称降序" value="name_desc" />
      </el-select>
      <span class="toolbar-count">{{ filteredCases.length }} / {{ caseStore.cases.length }}</span>
    </div>

    <div v-if="caseStore.loading && caseStore.cases.length === 0" class="page-loading">
      <div class="skeleton-grid">
        <el-skeleton v-for="i in 6" :key="i" :rows="3" animated :throttle="300" />
      </div>
    </div>

    <div v-else-if="caseStore.cases.length === 0" class="empty-state">
      <p class="empty-text">暂无案件</p>
      <p class="empty-hint">点击「新建案件」开始调查</p>
      <div class="empty-actions">
        <el-button type="primary" @click="showCreate = true">新建案件</el-button>
      </div>
    </div>

    <div v-else-if="isEmptyAfterFilter" class="empty-state">
      <p class="empty-text">没有匹配的案件</p>
      <p class="empty-hint">调整筛选条件，或清除搜索</p>
      <el-button @click="resetFilters">清除筛选</el-button>
    </div>

    <div v-else class="case-body" v-loading="caseStore.loading">
      <div class="case-grid">
        <CaseCard
          v-for="c in filteredCases"
          :key="c.id"
          :name="c.name"
          :case-number="c.case_number"
          :status="c.status"
          :created-at="c.created_at"
          @click="handleEnter(c.id)"
          @delete="handleDelete(c.id)"
          @rename="handleRename(c.id)"
        />
      </div>
      <div v-if="caseStore.total > 0" class="case-pager">
        <el-pagination
          v-model:current-page="caseStore.page"
          v-model:page-size="caseStore.pageSize"
          :total="caseStore.total"
          :page-sizes="[12, 24, 48]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="(p: number) => caseStore.fetchCases(p)"
          @size-change="() => caseStore.fetchCases(1)"
        />
      </div>
    </div>

    <el-dialog v-model="showCreate" title="新建案件" width="480px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="案件名称" required>
          <el-input v-model="createForm.name" placeholder="请输入案件名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="案件编号">
          <el-input v-model="createForm.case_number" placeholder="选填" maxlength="50" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.note" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!createForm.name.trim()" @click="handleCreate">
          创建案件
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.case-list-page { padding: 8px 0; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  gap: 16px;
  flex-wrap: wrap;
}
.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.toolbar-search {
  width: 320px;
  max-width: 100%;
}
.toolbar-status,
.toolbar-sort {
  width: 150px;
}
.toolbar-count {
  margin-left: auto;
  font-size: 13px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.case-body {
  min-height: 200px;
}
.case-pager {
  display: flex;
  justify-content: center;
  margin-top: 28px;
  padding-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--app-text);
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 14px;
  color: var(--app-text-secondary);
}
.case-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}
.empty-state {
  text-align: center;
  padding: 80px 16px;
  background: var(--app-bg-card);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius);
}
.empty-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 6px;
}
.empty-hint {
  font-size: 14px;
  color: var(--app-text-secondary);
  margin: 0 0 20px;
}
.empty-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.page-loading { padding: 20px 0; }

@media (max-width: 640px) {
  .toolbar-search {
    width: 100%;
  }
  .toolbar-status,
  .toolbar-sort {
    width: 48%;
  }
}
</style>
