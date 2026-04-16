import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
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
        component: () => import('../views/CaseList.vue'),
      },
      {
        path: 'cases/:caseId/import',
        name: 'DataImport',
        meta: { title: '数据导入' },
        component: () => import('../views/DataImport.vue'),
      },
      {
        path: 'cases/:caseId/analyze',
        name: 'StartAnalysis',
        meta: { title: '开始分析' },
        component: () => import('../views/StartAnalysis.vue'),
      },
      {
        path: 'cases/:caseId/network',
        name: 'RelationshipNetwork',
        meta: { title: '关系网络' },
        component: () => import('../views/RelationshipNetwork.vue'),
      },
      {
        path: 'cases/:caseId/risk',
        name: 'RiskProfile',
        meta: { title: '风险画像' },
        component: () => import('../views/RiskProfile.vue'),
      },
      {
        path: 'cases/:caseId/persons/:personId/portrait',
        name: 'PersonPortrait',
        meta: { title: '人物画像' },
        component: () => import('../views/PortraitPage.vue'),
      },
      {
        path: 'cases/:caseId/clues/:clueId',
        name: 'ClueDetail',
        meta: { title: '线索详情' },
        component: () => import('../views/ClueDetailPage.vue'),
      },
      {
        path: 'cases/:caseId/report',
        name: 'InvestigationReport',
        meta: { title: '调查报告' },
        component: () => import('../views/InvestigationReport.vue'),
      },
      {
        path: 'admin/users',
        name: 'UserAdmin',
        meta: { title: '用户管理', roles: ['admin'] },
        component: () => import('../views/Users.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
