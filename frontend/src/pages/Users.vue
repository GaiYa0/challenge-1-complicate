<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { deleteUser, fetchUsers, type UserListItem } from '../api/users'
import Permission from '../components/Permission.vue'
import { useUserStore } from '../store/user'
import { isMessageBoxDismiss } from '../utils/elMessageBox'
import { notifyError, notifySuccess, notifyWarning } from '../utils/notify'

const userStore = useUserStore()
const list = ref<UserListItem[]>([])
const loading = ref(false)
const batchLoading = ref(false)
const rowDeletingId = ref<number | null>(null)

async function loadList() {
  loading.value = true
  try {
    list.value = await fetchUsers()
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadList()
})

async function handleDelete(row: UserListItem) {
  rowDeletingId.value = row.id
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteUser(row.id)
    notifySuccess('已删除')
    await loadList()
  } catch (e) {
    if (isMessageBoxDismiss(e)) return
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
  const ids = list.value.map((u) => u.id).filter((id) => id !== userStore.userInfo?.id)
  if (ids.length === 0) {
    notifyWarning('除当前账号外没有其他用户可删除')
    return
  }
  batchLoading.value = true
  try {
    await ElMessageBox.confirm(`将删除 ${ids.length} 个用户（已排除当前登录账号），是否继续？`, '批量删除', {
      type: 'warning',
    })
    for (const id of ids) {
      await deleteUser(id)
    }
    notifySuccess(`已删除 ${ids.length} 个用户`)
    await loadList()
  } catch (e) {
    if (isMessageBoxDismiss(e)) return
    notifyError('批量删除失败')
  } finally {
    batchLoading.value = false
  }
}
</script>

<template>
  <div class="users-page">
    <h1 class="page-title">用户管理</h1>

    <el-card shadow="hover" class="card" v-loading="loading">
      <template #header>
        <div class="card-head">
          <span>用户列表</span>
          <div class="card-actions">
            <el-button size="small" @click="loadList">刷新</el-button>
            <Permission role="admin">
              <el-button
                type="danger"
                size="small"
                :loading="batchLoading"
                :disabled="batchLoading || loading"
                @click="handleBatchDelete"
              >
                批量删除
              </el-button>
            </Permission>
          </div>
        </div>
      </template>
      <el-table :data="list" stripe border style="width: 100%">
        <template #empty>
          <el-empty description="暂无用户数据" />
        </template>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" size="small" disabled>编辑</el-button>
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

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
  margin: 0 0 20px;
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
  flex-wrap: wrap;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
