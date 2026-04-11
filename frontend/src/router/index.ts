import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

/**
 * 路由表集中管理；meta.roles 与 userStore.userInfo.role 对齐做 RBAC。
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../pages/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        meta: { title: '工作台' },
        component: () => import('../pages/Dashboard.vue'),
      },
      {
        path: 'analysis',
        name: 'Analysis',
        meta: { title: '数据分析' },
        component: () => import('../pages/Analysis.vue'),
      },
      {
        path: 'users',
        name: 'UserAdmin',
        meta: { title: '用户管理', roles: ['admin'] },
        component: () => import('../pages/Users.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
