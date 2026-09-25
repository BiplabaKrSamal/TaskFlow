import type { Priority, Role, Status, UserRef } from '../api/types'
import { PRIORITY_LABEL, STATUS_LABEL, initials } from '../lib/format'

export function Person({ user, empty = 'Unassigned' }: { user: UserRef | null; empty?: string }) {
  if (!user) return <span className="dim">{empty}</span>
  return (
    <span className="person">
      <span className="avatar" aria-hidden="true">
        {initials(user.name)}
      </span>
      {user.name}
    </span>
  )
}

export function StatusTag({ status }: { status: Status }) {
  return <span className={`tag status-${status}`}>{STATUS_LABEL[status]}</span>
}

export function PriorityTag({ priority }: { priority: Priority }) {
  return <span className={`tag priority-${priority}`}>{PRIORITY_LABEL[priority]}</span>
}

export function RoleTag({ role }: { role: Role }) {
  return <span className={`tag role-${role}`}>{role === 'owner' ? 'Owner' : 'Member'}</span>
}

interface PagerProps {
  page: number
  pages: number
  total: number
  noun: string
  onPage: (page: number) => void
  busy?: boolean
}

export function Pager({ page, pages, total, noun, onPage, busy }: PagerProps) {
  return (
    <nav className="pager" aria-label="Pagination">
      <span className="dim">
        {total} {total === 1 ? noun : `${noun}s`}
      </span>
      <span className="pager-controls">
        <button type="button" className="btn small" onClick={() => onPage(page - 1)} disabled={page <= 1 || busy}>
          Previous
        </button>
        <span className="pager-page">
          Page {page} of {pages}
        </span>
        <button type="button" className="btn small" onClick={() => onPage(page + 1)} disabled={page >= pages || busy}>
          Next
        </button>
      </span>
    </nav>
  )
}
