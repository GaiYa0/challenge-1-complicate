import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { TENANT_STORAGE_KEY, TOKEN_STORAGE_KEY } from '../constants/auth'
import { notifyError, notifyWarning } from '../utils/notify'
import router from '../router'

/** 后端统一响应（与 FastAPI UnifiedResponse 对齐） */
export interface ApiEnvelope<T = unknown> {
  code: number
  msg: string
  data: T | null
  request_id?: string
}

function isApiEnvelope(v: unknown): v is ApiEnvelope {
  return (
    typeof v === 'object' &&
    v !== null &&
    'code' in v &&
    typeof (v as ApiEnvelope).code === 'number' &&
    'msg' in v &&
    typeof (v as ApiEnvelope).msg === 'string'
  )
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

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
    return config
  },
  (error) => Promise.reject(error),
)

http.interceptors.response.use(
  (response) => {
    const body = response.data as unknown
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
  (error: AxiosError<ApiEnvelope>) => {
    const silent = Boolean(error.config?.silentError)
    const status = error.response?.status
    const data = error.response?.data

    const message =
      (isApiEnvelope(data) && data.msg) ||
      error.message ||
      '请求失败'

    if (status === 401) {
      const msg = isApiEnvelope(data) ? data.msg : '登录已失效，请重新登录'
      const onLogin = router.currentRoute.value.path === '/login'
      /** 登录页上的失败请求（如密码错误）由页面统一提示，避免与拦截器重复弹窗 */
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
      console.error('[HTTP 500]', msg)
      if (!silent) notifyError(`服务器错误：${msg}`)
      return Promise.reject(new Error(msg))
    }

    if (!error.response) {
      const hint =
        error.code === 'ECONNABORTED'
          ? '请求超时，请检查网络或后端服务'
          : '网络异常，无法连接服务器'
      console.error('[Network]', error.message)
      if (!silent) notifyError(hint)
      return Promise.reject(new Error(hint))
    }

    if (status && status >= 400 && !silent) {
      notifyError(message)
    } else if (!status && !silent && message) {
      notifyError(message)
    }

    return Promise.reject(new Error(message))
  },
)

export default http
