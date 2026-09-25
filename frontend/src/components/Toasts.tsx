import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'

interface Toast {
  id: number
  kind: 'info' | 'error'
  text: string
}
interface ToastApi {
  info: (text: string) => void
  error: (text: string) => void
}

const Context = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), [])
  const push = useCallback(
    (kind: Toast['kind'], text: string) => {
      const id = nextId.current++
      setToasts((all) => [...all.slice(-3), { id, kind, text }])
      window.setTimeout(() => dismiss(id), kind === 'error' ? 8000 : 5000)
    },
    [dismiss],
  )
  const api = useMemo<ToastApi>(
    () => ({ info: (text) => push('info', text), error: (text) => push('error', text) }),
    [push],
  )

  return (
    <Context.Provider value={api}>
      {children}
      <div className="toasts" role="region" aria-label="Notifications" aria-live="polite">
        {toasts.map((toast) => (
          <button key={toast.id} type="button" className={`toast ${toast.kind}`} onClick={() => dismiss(toast.id)}>
            {toast.text}
          </button>
        ))}
      </div>
    </Context.Provider>
  )
}

export function useToast(): ToastApi {
  const value = useContext(Context)
  if (!value) throw new Error('useToast must be used inside <ToastProvider>')
  return value
}
