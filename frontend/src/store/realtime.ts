import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createRealtimeWebSocket, resolveDefaultWsUrl } from '../utils/websocket'
import { useDataStore } from './data'

/**
 * 全局单例 WebSocket：在 MainLayout 挂载时 start，卸载时 stop。
 * 消息一律交给 dataStore.applyRealtimeMessage，禁止页面直接改图表数据。
 */
export const useRealtimeStore = defineStore('realtime', () => {
  const connected = ref(false)
  const lastError = ref<string | null>(null)

  let client: ReturnType<typeof createRealtimeWebSocket> | null = null

  function start() {
    if (client) {
      client.disconnect()
      client = null
    }
    const url = import.meta.env.VITE_WS_URL || resolveDefaultWsUrl()
    client = createRealtimeWebSocket({
      url,
      maxReconnectAttempts: 12,
      onOpen: () => {
        connected.value = true
        lastError.value = null
      },
      onClose: () => {
        connected.value = false
      },
      onError: () => {
        lastError.value = '连接异常'
      },
      onMessage: (msg) => {
        useDataStore().applyRealtimeMessage(msg)
      },
      onMaxReconnect: () => {
        lastError.value = '已停止重连'
        ElMessage.error('实时通道多次重连失败，请检查网络或后端 /ws')
      },
    })
    client.connect()
  }

  function stop() {
    client?.disconnect()
    client = null
    connected.value = false
  }

  return { connected, lastError, start, stop }
})
