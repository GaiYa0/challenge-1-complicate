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
        meta: { title: '案件管理', keepAlive: true },
        component: () => import('../views/CaseList.vue'),
      },
      {
        path: 'cases/:caseId/import',
        name: 'DataImport',
        meta: { title: '数据导入' },
        component: () => import('../views/DataImport.vue'),
      },
      {
        path: 'cases/:caseId/cleaning',
        name: 'DataCleaning',
        meta: { title: '数据清洗' },
        component: () => import('../views/StartAnalysis.vue'),
      },
      {
        path: 'cases/:caseId/network',
        name: 'RelationshipNetwork',
        meta: { title: '证据关系图' },
        component: () => import('../views/RelationshipNetwork.vue'),
      },
      {
        path: 'cases/:caseId/portraits',
        name: 'PortraitList',
        meta: { title: '证据链分析' },
        component: () => import('../views/PortraitList.vue'),
      },
      {
        path: 'cases/:caseId/persons/:personId/portrait',
        name: 'PersonPortrait',
        meta: { title: '证据链详情' },
        component: () => import('../views/PortraitPage.vue'),
      },
      {
        path: 'cases/:caseId/portrait/compare',
        name: 'PortraitCompare',
        meta: { title: '画像对比' },
        component: () => import('../views/PortraitCompare.vue'),
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
        meta: { title: '证据报告' },
        component: () => import('../views/InvestigationReport.vue'),
      },
      {
        path: 'network/global',
        name: 'GlobalNetwork',
        meta: { title: '全局关系网络', keepAlive: true },
        component: () => import('../views/GlobalNetwork.vue'),
      },
      {
        path: 'admin/users',
        name: 'UserAdmin',
        meta: { title: '用户管理', roles: ['admin'], keepAlive: true },
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
