import type { Router } from 'vue-router'
import { useUiStore } from '../store/ui'
import { notifyWarning } from '../utils/notify'
import { useUserStore } from '../store/user'

/** 在 main.ts 中于 app.use(router) 之后调用，避免 router↔store 循环依赖 */
export function setupRouterGuard(router: Router) {
  const ui = useUiStore()

  router.beforeEach(async (to) => {
    if (to.name !== 'Login') {
      ui.startPageLoading()
    }

    const userStore = useUserStore()
    const hasToken = !!userStore.token

    if (to.name === 'Login') {
      if (hasToken) return { path: '/dashboard' }
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
        notifyWarning('无权访问该页面，已返回工作台')
        return { path: '/dashboard' }
      }
    }

    return true
  })

  router.afterEach(() => {
    ui.endPageLoading()
  })
}
