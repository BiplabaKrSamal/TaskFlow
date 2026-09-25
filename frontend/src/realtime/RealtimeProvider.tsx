import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useMatch, useNavigate, type NavigateFunction } from 'react-router-dom'
import { ensureToken } from '../api/client'
import type { LiveMessage } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useToast } from '../components/Toasts'
import { describe } from '../lib/activity'
import { LiveSocket, type LiveStatus } from './socket'

const Context = createContext<LiveStatus>('offline')

export function useLiveStatus(): LiveStatus {
  return useContext(Context)
}

type Toast = ReturnType<typeof useToast>
interface Latest {
  meId: string | undefined
  viewing: string | undefined
  client: QueryClient
  toast: Toast
  navigate: NavigateFunction
}

function react(message: LiveMessage, { meId, viewing, client, toast, navigate }: Latest): void {
  // Every event means something in a project changed: whatever shows it refetches.
  // Keeping the board, the lists and the counters in step is simpler than patching caches by hand.
  if (message.project_id) void client.invalidateQueries({ queryKey: ['project', message.project_id] })
  void client.invalidateQueries({ queryKey: ['projects'] })
  void client.invalidateQueries({ queryKey: ['me'] })

  if (message.type === 'removed_from_project' || message.type === 'project_deleted') {
    const gone = message.project_id !== undefined && message.project_id === viewing
    if (gone) navigate('/')
    toast.info(
      message.type === 'project_deleted'
        ? `“${message.project_name ?? 'A project'}” was deleted`
        : 'You no longer have access to a project',
    )
    return
  }

  const actor = message.actor
  if (!actor || actor.id === meId) return // your own actions already show on screen
  if (message.type === 'task_updated') return // small edits are visible on the board without a toast
  toast.info(describe(message.type, actor.name, message.meta ?? {}, meId))
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const client = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const viewing = useMatch('/projects/:projectId/*')?.params.projectId
  const [status, setStatus] = useState<LiveStatus>('offline')

  // The socket outlives renders, so it reads the latest values through a ref.
  const latest = useRef<Latest>({ meId: user?.id, viewing, client, toast, navigate })
  latest.current = { meId: user?.id, viewing, client, toast, navigate }

  const meId = user?.id
  useEffect(() => {
    if (!meId) return
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new LiveSocket({
      url: `${scheme}://${window.location.host}/api/ws`,
      getToken: ensureToken,
      onStatus: setStatus,
      onMessage: (message) => react(message, latest.current),
      onResync: () => void latest.current.client.invalidateQueries(),
    })
    socket.start()
    return () => socket.stop()
  }, [meId])

  return <Context.Provider value={status}>{children}</Context.Provider>
}
