<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Permission from '../components/Permission.vue'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()

function handlePageBack() {
  router.back()
}
const pageLoading = ref(true)

onMounted(async () => {
  pageLoading.value = true
  try {
    await userStore.fetchHealth()
  } finally {
    pageLoading.value = false
  }
})
</script>

<template>
  <div class="dash-page" v-loading="pageLoading">
    <el-page-header content="工作台" @back="handlePageBack" />
    <p class="dash-desc">
      当前用户：
      <strong>{{ userStore.userInfo?.name ?? '—' }}</strong>
      · 角色 <el-tag size="small">{{ userStore.userInfo?.role ?? '—' }}</el-tag>
      · 租户 <code>{{ userStore.userInfo?.tenant_id ?? '—' }}</code>
    </p>
    <p v-if="userStore.healthStatus" class="dash-health">
      服务健康：<el-tag type="success" size="small">{{ userStore.healthStatus }}</el-tag>
    </p>

    <el-row :gutter="16" class="dash-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="dash-card">
          <template #header>
            <span>快捷入口</span>
          </template>
          <el-space wrap>
            <el-button type="primary" tag="router-link" to="/analysis">数据分析</el-button>
            <el-button tag="router-link" to="/users">用户管理</el-button>
          </el-space>
          <p class="dash-hint">无权限用户点击「用户管理」将被路由守卫拦截并提示。</p>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="dash-card">
          <template #header>
            <span>按钮级权限演示</span>
          </template>
          <el-space>
            <el-button type="primary" plain>所有人可见</el-button>
            <Permission role="admin">
              <el-button type="danger" plain>仅管理员可见 · 删除</el-button>
            </Permission>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dash-page {
  max-width: 960px;
  margin: 0 auto;
  min-height: 240px;
}

.dash-desc {
  margin: 12px 0 8px;
  font-size: 14px;
  color: var(--app-text-secondary);
  line-height: 1.6;
}

.dash-desc code {
  font-size: 12px;
  padding: 2px 6px;
  background: var(--app-bg-layout);
  border-radius: 4px;
}

.dash-health {
  margin: 0 0 20px;
  font-size: 14px;
  color: var(--app-text-secondary);
}

.dash-row {
  margin-top: 8px;
}

.dash-card {
  border-radius: var(--app-radius);
  border-color: var(--app-border);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.dash-card:hover {
  box-shadow: var(--app-shadow-hover);
  transform: translateY(-2px);
}

.dash-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--app-text-secondary);
}
</style>
