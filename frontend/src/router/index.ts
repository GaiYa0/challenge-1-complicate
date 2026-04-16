import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../pages/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../layouts/InvestigationLayout.vue'),
    redirect: '/cases',
    children: [
      {
        path: 'cases',
        name: 'CaseList',
        meta: { title: '案件管理' },
        component: () => import('../pages/CaseList.vue'),
      },
      {
        path: 'cases/:caseId/import',
        name: 'DataImport',
        meta: { title: '数据导入' },
        component: () => import('../pages/DataImport.vue'),
      },
      {
        path: 'cases/:caseId/analyze',
        name: 'StartAnalysis',
        meta: { title: '开始分析' },
        component: () => import('../pages/StartAnalysis.vue'),
      },
      {
        path: 'cases/:caseId/network',
        name: 'RelationshipNetwork',
        meta: { title: '关系网络' },
        component: () => import('../pages/RelationshipNetwork.vue'),
      },
      {
        path: 'cases/:caseId/risk',
        name: 'RiskProfile',
        meta: { title: '风险画像' },
        component: () => import('../pages/RiskProfile.vue'),
      },
      {
        path: 'cases/:caseId/report',
        name: 'InvestigationReport',
        meta: { title: '调查报告' },
        component: () => import('../pages/InvestigationReport.vue'),
      },
      {
        path: 'admin/users',
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
