<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Moon, Sunny, ArrowRight } from '@element-plus/icons-vue'
import { useUserStore } from '../store/user'
import { useUiStore } from '../store/ui'
import { useRealtimeStore } from '../store/realtime'
import { useCaseStore } from '../store/case'
import { useThemeStore } from '../store/modules/theme.store'
import ErrorBoundary from '../components/common/ErrorBoundary.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const uiStore = useUiStore()
const realtimeStore = useRealtimeStore()
const caseStore = useCaseStore()
const themeStore = useThemeStore()

const currentCaseId = computed(() => {
  const raw = route.params.caseId
  return raw ? Number(raw) : null
})

const caseName = computed(() => caseStore.currentCase?.name ?? '')

interface MenuItem {
  path: string
  title: string
  level: 'top' | 'case'
}

const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    { path: '/cases', title: '案件管理', level: 'top' },
  ]
  const cid = currentCaseId.value
  if (cid) {
    items.push(
      { path: `/cases/${cid}/import`, title: '数据导入', level: 'case' },
      { path: `/cases/${cid}/cleaning`, title: '数据清洗', level: 'case' },
      { path: `/cases/${cid}/network`, title: '证据关系图', level: 'case' },
      { path: `/cases/${cid}/portraits`, title: '证据链分析', level: 'case' },
      { path: `/cases/${cid}/report`, title: '证据报告', level: 'case' },
    )
  }
  items.push({ path: '/network/global', title: '全局关系网络', level: 'top' })
  if (userStore.isAdmin) {
    items.push({ path: '/admin/users', title: '用户管理', level: 'top' })
  }
  return items
})

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

const keepAliveNames = computed<string[]>(() => {
  const names = new Set<string>()
  for (const r of router.getRoutes()) {
    if (r.meta?.keepAlive && typeof r.name === 'string') names.add(r.name)
  }
  return Array.from(names)
})

interface Crumb { label: string; to?: string }
const breadcrumbs = computed<Crumb[]>(() => {
  const items: Crumb[] = [{ label: '案件管理', to: '/cases' }]
  if (currentCaseId.value && caseName.value) {
    items.push({
      label: caseName.value,
      to: `/cases/${currentCaseId.value}/import`,
    })
  }
  const title = typeof route.meta.title === 'string' ? route.meta.title : ''
  if (title && title !== '案件管理') items.push({ label: title })
  return items
})

const drawerVisible = ref(false)
function openDrawer() { drawerVisible.value = true }

function handleMenuSelect(index: string) {
  drawerVisible.value = false
  if (index && typeof index === 'string') router.push(index)
}
</script>

<template>
  <el-container class="layout-root">
    <el-aside class="layout-aside layout-aside-desktop" :width="'var(--app-aside-w)'">
      <div class="aside-brand">检察调查辅助系统</div>
      <nav class="aside-nav">
        <template v-for="item in menuItems" :key="item.path">
          <!-- 案件子项前加分组标题 -->
          <div
            v-if="item.level === 'case' && item.path.endsWith('/import')"
            class="nav-group-label"
          >
            {{ caseName || '当前案件' }}
          </div>
          <router-link
            :to="item.path"
            class="nav-item"
            :class="{
              'nav-item--case': item.level === 'case',
              'nav-item--top': item.level === 'top',
              'nav-item--active': route.path === item.path
                || (item.path.endsWith('/portraits') && route.path.includes('/persons/'))
            }"
            active-class=""
          >
            {{ item.title }}
          </router-link>
          <!-- 案件子项结束后加分割线 -->
          <div
            v-if="item.level === 'case' && item.path.endsWith('/report')"
            class="nav-divider"
          />
        </template>
      </nav>
    </el-aside>

    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="260px"
      :with-header="false"
      class="layout-drawer"
    >
      <div class="aside-brand">检察调查辅助系统</div>
      <nav class="aside-nav">
        <template v-for="item in menuItems" :key="item.path">
          <div
            v-if="item.level === 'case' && item.path.endsWith('/import')"
            class="nav-group-label"
          >
            {{ caseName || '当前案件' }}
          </div>
          <a
            class="nav-item"
            :class="{
              'nav-item--case': item.level === 'case',
              'nav-item--top': item.level === 'top',
              'nav-item--active': route.path === item.path
            }"
            @click.prevent="handleMenuSelect(item.path)"
          >
            {{ item.title }}
          </a>
          <div
            v-if="item.level === 'case' && item.path.endsWith('/report')"
            class="nav-divider"
          />
        </template>
      </nav>
    </el-drawer>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-button text class="drawer-trigger" @click="openDrawer" aria-label="展开导航">
            &#9776;
          </el-button>
          <nav class="breadcrumb" aria-label="breadcrumb">
            <template v-for="(b, idx) in breadcrumbs" :key="idx">
              <router-link v-if="b.to && idx !== breadcrumbs.length - 1" :to="b.to" class="crumb crumb-link">
                {{ b.label }}
              </router-link>
              <span v-else class="crumb crumb-current">{{ b.label }}</span>
              <el-icon v-if="idx < breadcrumbs.length - 1" class="crumb-sep">
                <ArrowRight />
              </el-icon>
            </template>
          </nav>
        </div>
        <div class="header-right">
          <el-tooltip :content="themeStore.mode === 'dark' ? '切换为浅色' : '切换为暗色'" placement="bottom">
            <el-button text circle @click="themeStore.toggle">
              <el-icon :size="18">
                <Moon v-if="themeStore.mode === 'dark'" />
                <Sunny v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
          <span class="header-user">{{ userStore.userInfo?.name }}</span>
          <el-tag size="small" type="info">{{ userStore.userInfo?.role }}</el-tag>
          <el-button text size="small" @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <el-main class="layout-main" v-loading="uiStore.pageLoading">
        <ErrorBoundary>
          <router-view v-slot="{ Component, route: r }">
            <transition name="fade-slide" mode="out-in">
              <keep-alive :include="keepAliveNames">
                <component :is="Component" :key="r.meta?.keepAlive ? (r.name as string | undefined) : r.fullPath" />
              </keep-alive>
            </transition>
          </router-view>
        </ErrorBoundary>
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

/* ---- 自定义导航 ---- */
.aside-nav {
  padding: 8px 0;
}
.nav-group-label {
  padding: 14px 16px 6px 16px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-item {
  display: block;
  padding: 10px 20px;
  font-size: 14px;
  color: #cbd5e1;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
}
.nav-item--active {
  background: rgba(255, 255, 255, 0.12) !important;
  color: #ffffff !important;
  font-weight: 600;
  border-right: 3px solid #60a5fa;
}
.nav-item--top {
  font-weight: 500;
}
.nav-item--case {
  padding-left: 36px;
  font-size: 13px;
  color: #94a3b8;
}
.nav-item--case:hover {
  color: #e2e8f0;
}
.nav-item--case.nav-item--active {
  color: #ffffff !important;
}
.nav-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 6px 16px;
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
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.drawer-trigger {
  display: none;
  font-size: 18px;
  padding: 4px 8px;
}
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--app-text-secondary);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.crumb-link {
  color: var(--app-text-secondary);
  text-decoration: none;
  transition: color 0.18s ease;
}
.crumb-link:hover {
  color: var(--app-primary);
}
.crumb-current {
  color: var(--app-text);
  font-weight: 600;
}
.crumb-sep {
  color: var(--app-border);
  font-size: 14px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-user {
  font-size: 14px;
  color: var(--app-text);
}
.layout-main {
  background: var(--app-bg-layout);
  min-height: calc(100vh - var(--app-header-h));
  padding: 24px;
}

.layout-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: #1a365d;
}

@media (max-width: 860px) {
  .layout-aside-desktop {
    display: none;
  }
  .drawer-trigger {
    display: inline-flex;
  }
  .layout-header { padding: 0 12px; }
  .header-user { display: none; }
}
</style>
