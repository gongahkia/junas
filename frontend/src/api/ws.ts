import type { WsMessage } from "./types"

export type WsHandlers = {
  onMessage: (msg: WsMessage) => void
  onOpen?: () => void
  onClose?: (ev: CloseEvent) => void
  onError?: (ev: Event) => void
}

export class SessionSocket {
  private ws: WebSocket | null = null
  private url: string

  constructor(code: string, token: string) {
    const proto = location.protocol === "https:" ? "wss:" : "ws:"
    this.url = `${proto}//${location.host}/ws/sessions/${encodeURIComponent(code)}?token=${encodeURIComponent(token)}`
  }

  connect(handlers: WsHandlers): void {
    const ws = new WebSocket(this.url)
    this.ws = ws
    ws.onopen = () => handlers.onOpen?.()
    ws.onclose = (ev) => handlers.onClose?.(ev)
    ws.onerror = (ev) => handlers.onError?.(ev)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WsMessage
        handlers.onMessage(msg)
      } catch (e) {
        console.error("ws parse fail", e, ev.data)
      }
    }
  }

  send(type: string, payload: Record<string, unknown>): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return
    this.ws.send(JSON.stringify({ type, payload }))
  }

  close(): void {
    this.ws?.close()
    this.ws = null
  }
}
