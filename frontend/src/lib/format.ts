import type { Priority, Status } from '../api/types'

export const STATUSES: Status[] = ['todo', 'in_progress', 'done']
export const STATUS_LABEL: Record<Status, string> = { todo: 'To Do', in_progress: 'In Progress', done: 'Done' }

export const PRIORITIES: Priority[] = ['low', 'medium', 'high']
export const PRIORITY_LABEL: Record<Priority, string> = { low: 'Low', medium: 'Medium', high: 'High' }

/** Today in UTC as YYYY-MM-DD. The server judges due dates against the UTC date, so the form does too. */
export function todayUtc(): string {
  return new Date().toISOString().slice(0, 10)
}

const dayFormat = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' })
const stampFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

/** "2026-09-24" -> "24 Sep". Parsed as UTC so the day never shifts with the viewer's timezone. */
export function formatDay(day: string): string {
  return dayFormat.format(new Date(`${day}T00:00:00Z`))
}

export function formatStamp(iso: string): string {
  return stampFormat.format(new Date(iso))
}

export function isOverdue(due: string | null, status: Status): boolean {
  return due !== null && status !== 'done' && due < todayUtc()
}

export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (seconds < 45) return 'now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? '?').slice(0, 2)
  return letters.toUpperCase()
}
