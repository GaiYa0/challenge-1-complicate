import type { Router } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { useUiStore } from '../store/ui'
import { notifyWarning } from '../utils/notify'
import { useUserStore } from '../store/user'

NProgress.configure({ showSpinner: false, trickleSpeed: 180, minimum: 0.08 })

/** 在 main.ts 中于 app.use(router) 之后调用，避免 router↔store 循环依赖 */
export function setupRouterGuard(router: Router) {
  const ui = useUiStore()

  router.beforeEach(async (to) => {
    NProgress.start()
    if (to.name !== 'Login') {
      ui.startPageLoading()
    }

    const userStore = useUserStore()
    const hasToken = !!userStore.token

    if (to.name === 'Login') {
      if (hasToken) return { path: '/cases' }
      return true
    }

    if (!hasToken) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    if (!userStore.userInfo) {
      try {
        await userStore.fetchProfile()
      } catch {
        userStore.logout()
        return { path: '/login', query: { redirect: to.fullPath } }
      }
    }

    const rawRoles = to.meta.roles
    const need = Array.isArray(rawRoles) ? (rawRoles as string[]) : undefined
    if (need?.length) {
      const role = userStore.userInfo?.role
      if (!role || !need.includes(role)) {
        notifyWarning('无权访问该页面')
        return { path: '/cases' }
      }
    }

    return true
  })

  router.afterEach(() => {
    ui.endPageLoading()
    NProgress.done()
  })

  router.onError(() => {
    ui.endPageLoading()
    NProgress.done()
  })
}
