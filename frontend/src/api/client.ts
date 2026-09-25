import type { AuthResponse } from './types'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fields: Record<string, string> = {},
  ) {
    super(message)
  }
}

interface Options {
  method?: string
  body?: unknown
  query?: Record<string, string | number | null | undefined>
  /** Send the access token (default). Login, signup and refresh turn this off. */
  auth?: boolean
}

// The access token lives only in memory: nothing an XSS payload could read from storage.
// A page reload gets a new one from the httpOnly refresh cookie.
let accessToken: string | null = null
let expiresAt = 0
let refreshing: Promise<AuthResponse> | null = null
let sessionEnded: () => void = () => {}

export function onSessionEnded(handler: () => void): void {
  sessionEnded = handler
}

function store(auth: AuthResponse): void {
  accessToken = auth.access_token
  expiresAt = Date.now() + auth.expires_in * 1000
}

export function clearSession(): void {
  accessToken = null
  expiresAt = 0
}

function withQuery(path: string, query: Options['query']): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `${path}?${text}` : path
}

async function send(path: string, opts: Options): Promise<Response> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`
  try {
    return await fetch(`/api${withQuery(path, opts.query)}`, {
      method: opts.method ?? 'GET',
      headers,
      credentials: 'same-origin',
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'network', 'Could not reach the server. Check your connection and try again.')
  }
}

async function toError(res: Response): Promise<ApiError> {
  let body: { detail?: unknown; code?: unknown; fields?: unknown } | null = null
  try {
    body = await res.json()
  } catch {
    // not JSON (a proxy error page, say): fall through to the generic message
  }
  const message = typeof body?.detail === 'string' ? body.detail : `The request failed (${res.status}).`
  const fields = body?.fields && typeof body.fields === 'object' ? (body.fields as Record<string, string>) : {}
  return new ApiError(res.status, typeof body?.code === 'string' ? body.code : 'error', message, fields)
}

/**
 * Trade the refresh cookie for a new access token.
 *
 * Everything that needs a token at the same moment (a page firing five requests when the
 * old token expires, a reload while a socket reconnects) shares this one request. The server
 * rotates the refresh token on every use, so racing several refreshes would be wasteful at best.
 */
export function refreshSession(): Promise<AuthResponse> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await send('/auth/refresh', { method: 'POST', auth: false })
        if (!res.ok) throw await toError(res)
        const auth = (await res.json()) as AuthResponse
        store(auth)
        return auth
      } catch (err) {
        // A 401 means the cookie is gone, expired or revoked: the login is over.
        // A network failure is not the same thing, so it does not sign anyone out.
        if (err instanceof ApiError && err.status === 401) {
          clearSession()
          sessionEnded()
        }
        throw err
      } finally {
        refreshing = null
      }
    })()
  }
  return refreshing
}

/** A token that is valid right now, refreshing first if the current one is missing or about to lapse. */
export async function ensureToken(): Promise<string> {
  if (!accessToken || Date.now() > expiresAt - 10_000) await refreshSession()
  return accessToken as string
}

export async function authenticate(path: '/auth/login' | '/auth/signup', body: unknown): Promise<AuthResponse> {
  const res = await send(path, { method: 'POST', body, auth: false })
  if (!res.ok) throw await toError(res)
  const auth = (await res.json()) as AuthResponse
  store(auth)
  return auth
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  let res = await send(path, opts)
  if (res.status === 401 && opts.auth !== false) {
    // Expired or missing access token: refresh once and replay the request, invisibly.
    await refreshSession()
    res = await send(path, opts)
  }
  if (!res.ok) throw await toError(res)
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}
