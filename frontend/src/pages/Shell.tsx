import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { useLiveStatus } from '../realtime/RealtimeProvider'

const LIVE_LABEL = { live: 'Live', connecting: 'Connecting', offline: 'Offline, retrying' } as const

export function Shell() {
  const { user, logout } = useAuth()
  const live = useLiveStatus()
  const { pathname } = useLocation()
  const [leaving, setLeaving] = useState(false)

  const links = [
    { to: '/', label: 'Projects', active: pathname === '/' || pathname.startsWith('/projects') },
    { to: '/assigned', label: 'Assigned to me', active: pathname.startsWith('/assigned') },
    { to: '/dashboard', label: 'Dashboard', active: pathname.startsWith('/dashboard') },
  ]

  return (
    <>
      <header className="topbar">
        <Link to="/" className="wordmark">
          taskflow
        </Link>
        <nav aria-label="Main">
          {links.map((link) => (
            <Link key={link.to} to={link.to} aria-current={link.active ? 'page' : undefined}>
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-right">
          <span className="live" data-state={live} role="status">
            <span className="led" aria-hidden="true" />
            {LIVE_LABEL[live]}
          </span>
          <span className="who">{user?.name}</span>
          <button
            type="button"
            className="btn small"
            disabled={leaving}
            onClick={() => {
              setLeaving(true)
              void logout()
            }}
          >
            {leaving ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  )
}
