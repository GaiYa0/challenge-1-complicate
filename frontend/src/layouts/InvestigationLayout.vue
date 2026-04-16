<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import { useUiStore } from '../store/ui'
import { useRealtimeStore } from '../store/realtime'
import { useCaseStore } from '../store/case'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const uiStore = useUiStore()
const realtimeStore = useRealtimeStore()
const caseStore = useCaseStore()

const currentCaseId = computed(() => {
  const raw = route.params.caseId
  return raw ? Number(raw) : null
})

const caseName = computed(() => caseStore.currentCase?.name ?? '')

interface MenuItem { path: string; title: string; icon: string }

const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    { path: '/cases', title: '案件管理', icon: '&#128194;' },
  ]
  const cid = currentCaseId.value
  if (cid) {
    items.push(
      { path: `/cases/${cid}/import`, title: '数据导入', icon: '&#128228;' },
      { path: `/cases/${cid}/analyze`, title: '开始分析', icon: '&#128270;' },
      { path: `/cases/${cid}/network`, title: '关系网络', icon: '&#128279;' },
      {
        path: `/cases/${cid}/persons/${encodeURIComponent('张伟')}/portrait`,
        title: '人物画像',
        icon: '&#128483;',
      },
      { path: `/cases/${cid}/risk`, title: '风险画像', icon: '&#128100;' },
      { path: `/cases/${cid}/report`, title: '调查报告', icon: '&#128196;' },
    )
  }
  if (userStore.isAdmin) {
    items.push({ path: '/admin/users', title: '用户管理', icon: '&#9881;' })
  }
  return items
})

// Keep caseStore in sync with route
import { watch } from 'vue'
watch(currentCaseId, (id) => {
  if (id) caseStore.selectCase(id)
}, { immediate: true })

function handleLogout() {
  userStore.logout()
  router.push('/login')
}

onMounted(() => {
  if (userStore.token) realtimeStore.start()
})
onBeforeUnmount(() => {
  realtimeStore.stop()
})
</script>

<template>
  <el-container class="layout-root">
    <el-aside class="layout-aside" :width="'var(--app-aside-w)'">
      <div class="aside-brand">检察调查辅助系统</div>
      <el-menu
        :default-active="route.path"
        :router="true"
        background-color="#1a365d"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
        class="aside-menu"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <span class="menu-icon" v-html="item.icon" />
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <span class="header-title">{{ route.meta.title }}</span>
          <span v-if="caseName" class="header-case">&mdash; {{ caseName }}</span>
        </div>
        <div class="header-right">
          <span class="header-user">{{ userStore.userInfo?.name }}</span>
          <el-tag size="small" type="info">{{ userStore.userInfo?.role }}</el-tag>
          <el-button text size="small" @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <el-main class="layout-main" v-loading="uiStore.pageLoading">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-root {
  min-height: 100vh;
}
.layout-aside {
  background: #1a365d;
  overflow-y: auto;
  overflow-x: hidden;
}
.aside-brand {
  height: var(--app-header-h);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 1px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.aside-menu {
  border-right: none;
}
.menu-icon {
  margin-right: 8px;
  font-size: 16px;
}
.layout-header {
  height: var(--app-header-h);
  background: var(--app-bg-card);
  border-bottom: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
}
.header-case {
  font-size: 14px;
  color: var(--app-text-secondary);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-user {
  font-size: 14px;
  color: var(--app-text);
}
.layout-main {
  background: var(--app-bg-layout);
  min-height: calc(100vh - var(--app-header-h));
}
</style>
