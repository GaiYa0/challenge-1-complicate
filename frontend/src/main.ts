import { createPinia } from 'pinia'
import { createApp } from 'vue'
// Element Plus 按需样式：JS API 类组件（Message / MessageBox / Notification / Loading）
// 不在 <template> 里出现，resolver 抓不到，必须手工 import 对应 CSS。
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-notification.css'
import 'element-plus/theme-chalk/el-loading.css'
import 'element-plus/theme-chalk/el-overlay.css'
// Element Plus 官方暗色变量；配合 <html class="dark"> 自动生效。
import 'element-plus/theme-chalk/dark/css-vars.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { setupRouterGuard } from './router/guard'
import { useUserStore } from './store/user'
import { useThemeStore } from './store/modules/theme.store'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
setupRouterGuard(router)

// 未捕获的渲染/组件异常的顶层兜底（不影响 axios 拦截器的网络错误处理）
app.config.errorHandler = (err, _vm, info) => {
  console.error('[app.errorHandler]', info, err)
}

app.mount('#app')

// 主题：读取 localStorage / 系统偏好，提前把 html.dark 类挂上
useThemeStore(pinia)
useUserStore(pinia).hydrateFromStorage()
