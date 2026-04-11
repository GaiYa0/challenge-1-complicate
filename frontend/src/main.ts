import { createPinia } from 'pinia'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { setupRouterGuard } from './router/guard'
import { useUserStore } from './store/user'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
setupRouterGuard(router)
app.use(ElementPlus, { locale: zhCn, size: 'default' })
app.mount('#app')

useUserStore(pinia).hydrateFromStorage()
