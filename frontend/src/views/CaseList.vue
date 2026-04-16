<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCaseStore } from '../store/case'
import CaseCard from '../components/investigation/CaseCard.vue'
import { notifySuccess, notifyError } from '../utils/notify'
import { ElMessageBox } from 'element-plus'
import { isMessageBoxDismiss } from '../utils/elMessageBox'

const router = useRouter()
const caseStore = useCaseStore()

const showCreate = ref(false)
const createForm = ref({ name: '', case_number: '', note: '' })
const creating = ref(false)
const demoLoading = ref(false)

onMounted(() => {
  void caseStore.fetchCases(1)
})

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

function handleEnter(id: number) {
  caseStore.selectCase(id)
  router.push(`/cases/${id}/import`)
}

async function handleDemoCase() {
  demoLoading.value = true
  try {
    const c = await caseStore.addDemoCase()
    notifySuccess('已生成演示案件')
    router.push(`/cases/${c.id}/import`)
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '生成失败')
  } finally {
    demoLoading.value = false
  }
}
</script>

<template>
  <div class="case-list-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">案件管理</h1>
        <p class="page-subtitle">选择已有案件继续调查，或创建新案件</p>
      </div>
      <div class="header-actions">
        <el-button
          type="success"
          size="large"
          plain
          :loading="demoLoading"
          @click="handleDemoCase"
        >
          一键演示案例
        </el-button>
        <el-button type="primary" size="large" @click="showCreate = true">+ 新建案件</el-button>
      </div>
    </div>

    <div v-if="caseStore.loading && caseStore.cases.length === 0" class="page-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="caseStore.cases.length === 0" class="empty-state">
      <p class="empty-text">暂无案件，请点击"新建案件"开始调查</p>
    </div>

    <div v-else class="case-body" v-loading="caseStore.loading">
      <div class="case-grid">
        <CaseCard
          v-for="c in caseStore.cases"
          :key="c.id"
          :name="c.name"
          :case-number="c.case_number"
          :status="c.status"
          :created-at="c.created_at"
          @click="handleEnter(c.id)"
          @delete="handleDelete(c.id)"
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
  margin-bottom: 28px;
  gap: 16px;
  flex-wrap: wrap;
}
.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
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
.empty-state {
  text-align: center;
  padding: 80px 0;
}
.empty-text {
  font-size: 16px;
  color: var(--app-text-secondary);
}
.page-loading { padding: 40px 0; }
</style>
