<script setup lang="ts">
import { DataAnalysis, House, User } from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRealtimeStore } from '../store/realtime'
import { useUiStore } from '../store/ui'
import { useUserStore } from '../store/user'

const route = useRoute()
const userStore = useUserStore()
const uiStore = useUiStore()
const realtimeStore = useRealtimeStore()

onMounted(() => {
  if (userStore.token) realtimeStore.start()
})

onBeforeUnmount(() => {
  realtimeStore.stop()
})

const pageTitle = computed(() => (route.meta.title as string | undefined) || '控制台')

type MenuItem = { path: string; title: string; icon: Component; roles?: string[] }

/** 菜单与 RBAC 对齐：无 userInfo 时仅展示工作台，避免首屏闪烁误点 */
const menuItems = computed<MenuItem[]>(() => {
  const r = userStore.userInfo?.role
  const all: MenuItem[] = [
    { path: '/dashboard', title: '工作台', icon: House, roles: ['admin', 'user'] },
    { path: '/analysis', title: '数据分析', icon: DataAnalysis, roles: ['admin', 'user'] },
    { path: '/users', title: '用户管理', icon: User, roles: ['admin'] },
  ]
  if (!r) return all.filter((m) => m.path === '/dashboard')
  return all.filter((m) => !m.roles || m.roles.includes(r))
})
</script>

<template>
  <el-container class="layout-root">
    <el-aside width="220px" class="layout-aside">
      <div class="brand">数据分析平台</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#1e293b"
        text-color="#cbd5e1"
        active-text-color="#93c5fd"
        class="side-menu"
      >
        <el-menu-item v-for="m in menuItems" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="layout-right">
      <el-header class="layout-header" height="56px">
        <div class="header-left">
          <span class="header-title">{{ pageTitle }}</span>
          <span class="header-sub">RBAC · 多租户请求头</span>
        </div>
        <div v-if="userStore.userInfo" class="header-tags">
          <el-tag size="small" :type="realtimeStore.connected ? 'success' : 'info'">
            实时 {{ realtimeStore.connected ? '已连接' : '未连接' }}
          </el-tag>
          <el-tag v-if="realtimeStore.lastError" size="small" type="warning">{{ realtimeStore.lastError }}</el-tag>
          <el-tag size="small" type="info">{{ userStore.userInfo.name }}</el-tag>
          <el-tag size="small" :type="userStore.isAdmin ? 'danger' : 'success'">
            {{ userStore.userInfo.role }}
          </el-tag>
          <el-tag size="small" effect="plain">租户 {{ userStore.userInfo.tenant_id }}</el-tag>
        </div>
      </el-header>
      <el-main v-loading="uiStore.pageLoading" class="layout-main" element-loading-text="加载中…">
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
  background: var(--app-bg-layout);
}

.layout-aside {
  flex-shrink: 0;
  width: var(--app-aside-w);
  background: #1e293b;
  border-right: 1px solid var(--app-border);
  display: flex;
  flex-direction: column;
}

.brand {
  height: var(--app-header-h);
  display: flex;
  align-items: center;
  padding: 0 16px;
  font-weight: 600;
  font-size: 15px;
  color: #f8fafc;
  letter-spacing: 0.02em;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.side-menu {
  border-right: none;
  flex: 1;
}

.layout-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.layout-header {
  flex-shrink: 0;
  height: var(--app-header-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 24px;
  background: var(--app-bg-card);
  border-bottom: 1px solid var(--app-border);
  box-shadow: var(--app-shadow-card);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
}

.header-sub {
  font-size: 13px;
  color: var(--app-text-secondary);
}

.header-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.layout-main {
  flex: 1;
  min-height: 0;
  padding: 20px 24px 28px;
  background: var(--app-bg-layout);
  overflow: auto;
}
</style>
