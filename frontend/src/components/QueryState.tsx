import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ApiError } from '../api/client'

export function Loading({ label }: { label: string }) {
  return (
    <div className="state" role="status">
      Loading {label}
      <span className="cursor" aria-hidden="true" />
    </div>
  )
}

export function ErrorPanel({ error, onRetry, busy }: { error: unknown; onRetry?: () => void; busy?: boolean }) {
  const message = error instanceof ApiError ? error.message : 'Something went wrong while loading this.'
  return (
    <div className="state error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry} disabled={busy}>
          {busy ? 'Trying again…' : 'Try again'}
        </button>
      )}
    </div>
  )
}

interface Props<T> {
  query: UseQueryResult<T>
  /** What is being loaded, for the loading text: "Loading projects". */
  label: string
  children: (data: T) => ReactNode
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
}

/** One place that decides what a data-backed view shows: loading, failure, nothing yet, or the data. */
export function QueryState<T>({ query, label, children, isEmpty, empty }: Props<T>) {
  if (query.isPending) return <Loading label={label} />
  if (query.isError) return <ErrorPanel error={query.error} onRetry={() => void query.refetch()} busy={query.isFetching} />
  if (isEmpty?.(query.data)) return <>{empty}</>
  return <div className={query.isPlaceholderData ? 'is-stale' : undefined}>{children(query.data)}</div>
}
