/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端 API 根地址，如 http://localhost:8000 */
  readonly VITE_API_BASE_URL: string
  /** WebSocket 地址，如 ws://localhost:8000/ws；不填则由 VITE_API_BASE_URL 推导 */
  readonly VITE_WS_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

import type {} from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    /** 可访问该路由的角色；不声明则登录即可访问 */
    roles?: string[]
  }
}
