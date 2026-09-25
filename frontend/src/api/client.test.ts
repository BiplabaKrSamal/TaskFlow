import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, clearSession, ensureToken, onSessionEnded, refreshSession } from './client'

const user = { id: 'u1', name: 'Alice', email: 'alice@example.com' }
const auth = (token: string) => ({ access_token: token, token_type: 'bearer', expires_in: 900, user })

function reply(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

let calls: { url: string; auth: string | null }[]
let script: (url: string, n: number) => Response

function install(handler: typeof script) {
  calls = []
  script = handler
  vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
    const headers = (init.headers ?? {}) as Record<string, string>
    calls.push({ url, auth: headers.Authorization ?? null })
    return script(url, calls.length)
  })
}

beforeEach(() => {
  clearSession()
  onSessionEnded(() => {})
})

describe('transparent refresh', () => {
  it('replays a request once after a 401 with a fresh token', async () => {
    install((url, n) => {
      if (url === '/api/auth/refresh') return reply(200, auth('fresh'))
      return n === 1 ? reply(401, { detail: 'expired', code: 'token_expired' }) : reply(200, { ok: true })
    })

    await expect(api('/projects')).resolves.toEqual({ ok: true })

    expect(calls.map((c) => c.url)).toEqual(['/api/projects', '/api/auth/refresh', '/api/projects'])
    expect(calls[2].auth).toBe('Bearer fresh')
  })

  it('shares one refresh between requests that all fail at the same time', async () => {
    const attempts = new Map<string, number>()
    install((url) => {
      if (url === '/api/auth/refresh') return reply(200, auth('fresh'))
      const attempt = (attempts.get(url) ?? 0) + 1
      attempts.set(url, attempt)
      // every request is rejected the first time and served on the replay
      return attempt === 1 ? reply(401, { detail: 'expired', code: 'token_expired' }) : reply(200, { url })
    })

    const results = await Promise.all([api('/a'), api('/b'), api('/c')])

    expect(results).toEqual([{ url: '/api/a' }, { url: '/api/b' }, { url: '/api/c' }])
    expect(calls.filter((c) => c.url === '/api/auth/refresh')).toHaveLength(1)
  })

  it('ends the session when the refresh token is rejected', async () => {
    const ended = vi.fn()
    onSessionEnded(ended)
    install((url) =>
      url === '/api/auth/refresh'
        ? reply(401, { detail: 'Your session has expired. Sign in again.', code: 'session_expired' })
        : reply(401, { detail: 'expired', code: 'token_expired' }),
    )

    await expect(api('/projects')).rejects.toMatchObject({ status: 401, code: 'session_expired' })
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('does not sign anyone out because the network dropped during a refresh', async () => {
    const ended = vi.fn()
    onSessionEnded(ended)
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('failed to fetch')
    })

    await expect(refreshSession()).rejects.toMatchObject({ status: 0, code: 'network' })
    expect(ended).not.toHaveBeenCalled()
  })

  it('does not try to refresh when a login itself is rejected', async () => {
    install(() => reply(401, { detail: 'Invalid email or password', code: 'invalid_credentials' }))
    const { authenticate } = await import('./client')

    await expect(authenticate('/auth/login', { email: 'a@b.co', password: 'x' })).rejects.toBeInstanceOf(ApiError)
    expect(calls).toHaveLength(1)
  })
})

describe('errors', () => {
  it('carries the server message and per-field errors', async () => {
    install(() => reply(422, { detail: 'Title cannot be empty', code: 'validation_error', fields: { title: 'Title cannot be empty' } }))
    const error: unknown = await api('/projects/p/tasks', { method: 'POST', body: {} }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('Title cannot be empty')
    expect((error as ApiError).fields).toEqual({ title: 'Title cannot be empty' })
  })

  it('still produces a readable error when the response is not JSON', async () => {
    install(() => new Response('<html>Bad gateway</html>', { status: 502 }))
    await expect(api('/projects')).rejects.toMatchObject({ status: 502, message: 'The request failed (502).' })
  })

  it('treats 204 as an empty success', async () => {
    install(() => reply(204))
    await expect(api('/projects/p', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})

describe('ensureToken', () => {
  it('refreshes when there is no token and reuses it afterwards', async () => {
    install(() => reply(200, auth('minted')))
    expect(await ensureToken()).toBe('minted')
    expect(await ensureToken()).toBe('minted')
    expect(calls).toHaveLength(1)
  })
})
