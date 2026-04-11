<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import Permission from '../components/Permission.vue'
import { useUserStore } from '../store/user'
import { notifyError, notifySuccess, notifyWarning } from '../utils/notify'

const userStore = useUserStore()
const list = ref<{ id: number; name: string; role: string }[]>([])
const batchLoading = ref(false)
const rowDeletingId = ref<number | null>(null)

onMounted(() => {
  list.value = [
    { id: 1, name: '示例用户 A', role: 'user' },
    { id: 2, name: '示例用户 B', role: 'admin' },
  ]
})

async function handleDelete(row: { id: number; name: string }) {
  rowDeletingId.value = row.id
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    list.value = list.value.filter((u) => u.id !== row.id)
    notifySuccess('删除成功')
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    notifyError('删除失败')
  } finally {
    rowDeletingId.value = null
  }
}

async function handleBatchDelete() {
  if (!list.value.length) {
    notifyWarning('当前没有可删除的数据')
    return
  }
  batchLoading.value = true
  try {
    await ElMessageBox.confirm(`将删除全部 ${list.value.length} 条演示数据，是否继续？`, '批量删除', {
      type: 'warning',
    })
    list.value = []
    notifySuccess('批量删除成功')
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    notifyError('批量删除失败')
  } finally {
    batchLoading.value = false
  }
}
</script>

<template>
  <div class="users-page">
    <el-page-header content="用户管理" />
    <p class="desc">仅 <strong>admin</strong> 可访问本页；数据为前端占位，后续对接用户列表 API。</p>

    <el-card shadow="hover" class="card">
      <template #header>
        <div class="card-head">
          <span>用户列表</span>
          <Permission role="admin">
            <el-button type="danger" size="small" :loading="batchLoading" :disabled="batchLoading" @click="handleBatchDelete">
              批量删除（演示）
            </el-button>
          </Permission>
        </div>
      </template>
      <el-table :data="list" stripe border style="width: 100%">
        <template #empty>
          <el-empty description="暂无用户数据" />
        </template>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="用户名" />
        <el-table-column prop="role" label="角色" width="120" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" size="small">编辑</el-button>
            <Permission role="admin">
              <el-button
                link
                type="danger"
                size="small"
                :loading="rowDeletingId === row.id"
                :disabled="rowDeletingId != null && rowDeletingId !== row.id"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </Permission>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <p class="foot">当前登录：{{ userStore.userInfo?.name }}（{{ userStore.userInfo?.role }}）</p>
  </div>
</template>

<style scoped>
.users-page {
  max-width: 960px;
  margin: 0 auto;
}

.desc {
  margin: 12px 0 20px;
  font-size: 14px;
  color: var(--app-text-secondary);
  line-height: 1.6;
}

.card {
  border-radius: var(--app-radius);
  border-color: var(--app-border);
}

.foot {
  margin-top: 16px;
  font-size: 13px;
  color: var(--app-text-secondary);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
