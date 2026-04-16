/**
 * Axios 单例：鉴权头、统一解包、错误提示、全局 loading、request_id 记录。
 * 业务模块请通过 api/modules/* 调用，避免直接 import 本文件（便于 mock）。
 */

import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios'
import { TENANT_STORAGE_KEY, TOKEN_STORAGE_KEY } from '../constants/auth'
import { notifyError, notifyWarning } from '../utils/notify'
import router from '../router'
import { globalHttpContext } from '../state/httpContext'
import { extractRequestId, isApiEnvelope } from './envelope'
import type { ApiEnvelope } from './envelope'

export type { ApiEnvelope }

const RATE_LIMIT_MAX_RETRIES = 3
const RATE_LIMIT_DEFAULT_BACKOFF_MS = 1500
const RATE_LIMIT_JITTER_MS = 400

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)))
}

function parseRetryAfterMs(header: unknown, fallbackMs: number): number {
  if (typeof header !== 'string' || header.length === 0) return fallbackMs
  const asNum = Number(header)
  if (Number.isFinite(asNum) && asNum >= 0) {
    return Math.min(15_000, Math.max(200, Math.round(asNum * 1000)))
  }
  const asDate = Date.parse(header)
  if (Number.isFinite(asDate)) {
    const delta = asDate - Date.now()
    if (delta > 0) return Math.min(15_000, delta)
  }
  return fallbackMs
}

http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (config.data instanceof FormData) {
      delete config.headers?.['Content-Type']
    }
    const token = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (token) {
      config.headers = config.headers ?? {}
      config.headers.Authorization = `Bearer ${token}`
    }
    const tenant = localStorage.getItem(TENANT_STORAGE_KEY)
    if (tenant) {
      config.headers = config.headers ?? {}
      config.headers['X-Tenant-ID'] = tenant
    }
    if (!config.skipGlobalLoading) {
      globalHttpContext.startRequest()
    }
    return config
  },
  (error) => Promise.reject(error),
)

function endLoadingIfNeeded(config: InternalAxiosRequestConfig | undefined): void {
  if (config && !config.skipGlobalLoading) {
    globalHttpContext.endRequest()
  }
}

http.interceptors.response.use(
  (response) => {
    endLoadingIfNeeded(response.config)
    const body = response.data as unknown
    const rid = extractRequestId(body)
    if (rid) {
      globalHttpContext.setLastRequestId(rid)
    }
    if (isApiEnvelope(body)) {
      if (body.code !== 0) {
        const silent = Boolean(response.config?.silentError)
        if (!silent) notifyError(body.msg || '请求失败')
        return Promise.reject(new Error(body.msg || '请求失败'))
      }
      return body.data as never
    }
    return body as never
  },
  async (error: AxiosError<ApiEnvelope>) => {
    const cfg = (error.config ?? {}) as InternalAxiosRequestConfig
    const silent = Boolean(cfg.silentError)
    const status = error.response?.status
    const data = error.response?.data

    const rid = extractRequestId(data)
    if (rid) {
      globalHttpContext.setLastRequestId(rid)
    }

    if (status === 429 && cfg && cfg._rateLimitRetry !== false) {
      const attempt = Number(cfg._rateLimitRetryCount ?? 0)
      if (attempt < RATE_LIMIT_MAX_RETRIES) {
        const headers = error.response?.headers as Record<string, unknown> | undefined
        const retryHeader = headers?.['retry-after'] ?? headers?.['Retry-After']
        const base = parseRetryAfterMs(retryHeader, RATE_LIMIT_DEFAULT_BACKOFF_MS)
        const backoff =
          base * Math.pow(1.6, attempt) + Math.random() * RATE_LIMIT_JITTER_MS
        cfg._rateLimitRetryCount = attempt + 1
        endLoadingIfNeeded(cfg)
        await sleep(backoff)
        return http.request(cfg)
      }
    }

    endLoadingIfNeeded(cfg)

    const message =
      (isApiEnvelope(data) && data.msg) ||
      error.message ||
      '请求失败'

    if (status === 401) {
      const msg = isApiEnvelope(data) ? data.msg : '登录已失效，请重新登录'
      const onLogin = router.currentRoute.value.path === '/login'
      if (silent && onLogin) {
        return Promise.reject(new Error(msg))
      }
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      localStorage.removeItem(TENANT_STORAGE_KEY)
      void import('../store/user')
        .then(({ useUserStore }) => {
          useUserStore().$patch({ token: null, userInfo: null })
        })
        .catch(() => {})
      notifyError(msg)
      if (!onLogin) {
        void router.replace({ path: '/login' })
      }
      return Promise.reject(new Error(message))
    }

    if (status === 403) {
      const msg = isApiEnvelope(data) ? data.msg : '权限不足'
      if (!silent) notifyWarning(msg)
      return Promise.reject(new Error(msg))
    }

    if (status === 500) {
      const msg = isApiEnvelope(data) ? data.msg : '服务器内部错误'
      console.error('[HTTP 500]', msg, { request_id: rid })
      if (!silent) notifyError(`服务器错误：${msg}`)
      return Promise.reject(new Error(msg))
    }

    if (!error.response) {
      const hint =
        error.code === 'ECONNABORTED'
          ? '请求超时，请检查网络或后端服务'
          : '网络异常，无法连接服务器'
      console.error('[Network]', error.message, { request_id: rid })
      if (!silent) notifyError(hint)
      return Promise.reject(new Error(hint))
    }

    if (status === 429) {
      const msg = isApiEnvelope(data) ? data.msg : '请求过于频繁，请稍候重试'
      if (!silent) notifyWarning(msg)
      return Promise.reject(new Error(msg))
    }

    if (status && status >= 400 && !silent) {
      notifyError(message)
    } else if (!status && !silent && message) {
      notifyError(message)
    }

    return Promise.reject(new Error(message))
  },
)

export type HttpRequestConfig = AxiosRequestConfig & {
  silentError?: boolean
  skipGlobalLoading?: boolean
  _rateLimitRetry?: boolean
  _rateLimitRetryCount?: number
}

export default http
