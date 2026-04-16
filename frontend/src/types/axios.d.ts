import 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** 为 true 时不由拦截器自动弹出错误提示（页面自行处理） */
    silentError?: boolean
    /** 为 true 时不参与全局 loading 计数（如后台轮询） */
    skipGlobalLoading?: boolean
    /** 为 false 时关闭 429 自动退避重试；内部状态字段请勿手工设置 */
    _rateLimitRetry?: boolean
    _rateLimitRetryCount?: number
  }
  interface InternalAxiosRequestConfig {
    silentError?: boolean
    skipGlobalLoading?: boolean
    _rateLimitRetry?: boolean
    _rateLimitRetryCount?: number
  }
}
