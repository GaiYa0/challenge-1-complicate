import 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** 为 true 时不由拦截器自动弹出错误提示（页面自行处理） */
    silentError?: boolean
  }
}
