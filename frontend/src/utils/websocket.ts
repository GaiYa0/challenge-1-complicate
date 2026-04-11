/**
 * WebSocket 封装：统一重连退避、手动关闭与消息解析。
 * 页面禁止 `new WebSocket`，避免重复逻辑与泄漏。
 */

export type RealtimeMessage = {
  type: string
  data: unknown
}

export type RealtimeWsOptions = {
  url: string
  onMessage?: (msg: RealtimeMessage) => void
  onOpen?: () => void
  onClose?: (ev: CloseEvent) => void
  onError?: (ev: Event) => void
  /** 达到上限后不再重连 */
  onMaxReconnect?: () => void
  maxReconnectAttempts?: number
}

/** 由 HTTP API 根地址推导默认 ws://…/ws（支持同源相对路径如 `/api`） */
export function resolveDefaultWsUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  let httpBase: string
  if (base.startsWith('/')) {
    const origin =
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'http://localhost:8000'
    httpBase = `${origin}${base}`
  } else {
    httpBase = base
  }
  const u = new URL(httpBase)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = '/ws'
  u.search = ''
  u.hash = ''
  return u.toString()
}

export function createRealtimeWebSocket(opts: RealtimeWsOptions) {
  const max = opts.maxReconnectAttempts ?? 12
  let ws: WebSocket | null = null
  let manualClose = false
  let reconnectCount = 0
  let timer: ReturnType<typeof setTimeout> | null = null

  function clearTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function scheduleReconnect() {
    if (manualClose) return
    if (reconnectCount >= max) {
      console.error('[ws] 已达最大重连次数', max)
      opts.onMaxReconnect?.()
      return
    }
    reconnectCount += 1
    const delay = Math.min(30_000, 1000 * 2 ** (reconnectCount - 1))
    console.warn('[ws] 将在 ms 后重连:', delay, 'attempt', reconnectCount)
    clearTimer()
    timer = setTimeout(() => innerConnect(), delay)
  }

  function innerConnect() {
    clearTimer()
    try {
      ws = new WebSocket(opts.url)
    } catch (e) {
      console.error('[ws] 创建失败', e)
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      reconnectCount = 0
      opts.onOpen?.()
    }

    ws.onmessage = (ev) => {
      try {
        const raw = JSON.parse(String(ev.data)) as unknown
        if (!raw || typeof raw !== 'object' || !('type' in raw)) {
          console.warn('[ws] 非对象消息', raw)
          return
        }
        const msg = raw as RealtimeMessage
        opts.onMessage?.(msg)
      } catch (e) {
        console.warn('[ws] JSON 解析失败', e)
      }
    }

    ws.onerror = (ev) => {
      console.error('[ws] error 事件', ev)
      opts.onError?.(ev)
    }

    ws.onclose = (ev) => {
      opts.onClose?.(ev)
      ws = null
      if (!manualClose) scheduleReconnect()
    }
  }

  return {
    connect() {
      manualClose = false
      reconnectCount = 0
      innerConnect()
    },
    disconnect() {
      manualClose = true
      clearTimer()
      ws?.close()
      ws = null
    },
    get readyState() {
      return ws?.readyState ?? WebSocket.CLOSED
    },
  }
}
