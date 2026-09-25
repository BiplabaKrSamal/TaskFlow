import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, api, authenticate, clearSession, onSessionEnded, refreshSession } from '../api/client'
import type { User } from '../api/types'

// loading: asking the server who we are. unreachable: the server could not be asked at all.
type Status = 'loading' | 'authed' | 'anon' | 'unreachable'

interface AuthContext {
  user: User | null
  status: Status
  login: (email: string, password: string) => Promise<void>
  signup: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  retry: () => void
}

const Context = createContext<AuthContext | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<Status>('loading')

  // On every page load the access token is gone (it only lives in memory), so the first
  // thing to do is ask the server, using the refresh cookie, whether there is still a login.
  const boot = useCallback(async () => {
    setStatus('loading')
    try {
      const auth = await refreshSession()
      setUser(auth.user)
      setStatus('authed')
    } catch (err) {
      setUser(null)
      setStatus(err instanceof ApiError && err.status !== 0 ? 'anon' : 'unreachable')
    }
  }, [])

  useEffect(() => {
    // Refresh was refused mid-session: drop everything the previous login could see.
    onSessionEnded(() => {
      setUser(null)
      setStatus('anon')
      queryClient.clear()
    })
    void boot()
  }, [boot, queryClient])

  const value = useMemo<AuthContext>(
    () => ({
      user,
      status,
      retry: () => void boot(),
      login: async (email, password) => {
        const auth = await authenticate('/auth/login', { email, password })
        setUser(auth.user)
        setStatus('authed')
      },
      signup: async (name, email, password) => {
        const auth = await authenticate('/auth/signup', { name, email, password })
        setUser(auth.user)
        setStatus('authed')
      },
      logout: async () => {
        await api('/auth/logout', { method: 'POST', auth: false }).catch(() => undefined)
        clearSession()
        setUser(null)
        setStatus('anon')
        queryClient.clear()
      },
    }),
    [user, status, boot, queryClient],
  )

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useAuth(): AuthContext {
  const value = useContext(Context)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

export function useMe(): User {
  const { user } = useAuth()
  if (!user) throw new Error('useMe needs a signed-in user')
  return user
}
