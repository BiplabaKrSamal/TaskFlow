import type { LiveMessage } from '../api/types'

export type LiveStatus = 'connecting' | 'live' | 'offline'

interface Options {
  url: string
  getToken: () => Promise<string>
  onStatus: (status: LiveStatus) => void
  onMessage: (message: LiveMessage) => void
  /** Fired on every reconnect after the first: events may have been missed, so the app refetches. */
  onResync: () => void
}

const UNAUTHORIZED = 4401 // the server ended the socket because its token expired
const PING_EVERY = 25_000
const SILENCE_LIMIT = 60_000

/**
 * A websocket that keeps itself alive.
 *
 * Each connection starts with the access token as its first message. When the link drops,
 * for any reason, it reconnects with exponential backoff (plus jitter, so a restarted server
 * is not hit by every tab at once) and gets a fresh token first. The server keeps no history to replay,
 * so after reconnecting the app refetches instead of trying to patch over the gap.
 */
export class LiveSocket {
  private ws: WebSocket | null = null
  private attempt = 0
  private stopped = true
  private hasBeenLive = false
  private lastHeard = 0
  private retryTimer: ReturnType<typeof setTimeout> | undefined
  private heartbeat: ReturnType<typeof setInterval> | undefined

  constructor(private readonly options: Options) {}

  start(): void {
    this.stopped = false
    void this.connect()
  }

  stop(): void {
    this.stopped = true
    clearTimeout(this.retryTimer)
    clearInterval(this.heartbeat)
    const ws = this.ws
    this.ws = null
    ws?.close()
  }

  private async connect(): Promise<void> {
    if (this.stopped) return
    this.options.onStatus('connecting')

    let token: string
    try {
      token = await this.options.getToken()
    } catch {
      this.scheduleRetry(false)
      return
    }
    if (this.stopped) return

    const ws = new WebSocket(this.options.url)
    this.ws = ws
    ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token }))
    ws.onmessage = (event) => {
      this.lastHeard = Date.now()
      try {
        this.handle(JSON.parse(String(event.data)) as LiveMessage)
      } catch {
        // a malformed frame is not worth dropping the connection over
      }
    }
    ws.onerror = () => ws.close()
    ws.onclose = (event) => {
      if (this.ws !== ws) return // an old socket that was already replaced or stopped
      this.ws = null
      clearInterval(this.heartbeat)
      this.options.onStatus('offline')
      if (!this.stopped) this.scheduleRetry(event.code === UNAUTHORIZED)
    }
  }

  private handle(message: LiveMessage): void {
    if (message.type === 'pong') return
    if (message.type === 'ready') {
      this.attempt = 0
      this.options.onStatus('live')
      this.startHeartbeat()
      if (this.hasBeenLive) this.options.onResync()
      this.hasBeenLive = true
      return
    }
    this.options.onMessage(message)
  }

  private startHeartbeat(): void {
    clearInterval(this.heartbeat)
    this.lastHeard = Date.now()
    this.heartbeat = setInterval(() => {
      const ws = this.ws
      if (!ws) return
      // Half-open connections (a laptop that slept, a proxy that dropped the link silently)
      // never fire onclose, so silence is treated as a dead link.
      if (Date.now() - this.lastHeard > SILENCE_LIMIT) ws.close()
      else if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
    }, PING_EVERY)
  }

  private scheduleRetry(tokenExpired: boolean): void {
    // An expired token is the normal end of a connection, not a fault: come straight back with a new one.
    const wait =
      tokenExpired && this.attempt === 0 ? 0 : Math.min(30_000, 1000 * 2 ** this.attempt) * (0.5 + Math.random() / 2)
    this.attempt += 1
    clearTimeout(this.retryTimer)
    this.retryTimer = setTimeout(() => void this.connect(), wait)
  }
}
