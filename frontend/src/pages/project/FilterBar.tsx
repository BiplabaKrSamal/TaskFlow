import { useEffect, useState } from 'react'
import type { TaskFilters } from '../../api/hooks'
import type { Member, Priority, Status } from '../../api/types'
import { Field } from '../../components/Field'
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL } from '../../lib/format'

interface Props {
  members: Member[]
  filters: TaskFilters
  showStatus: boolean
  active: boolean
  onChange: (patch: Record<string, string | undefined>) => void
  onClear: () => void
}

export function FilterBar({ members, filters, showStatus, active, onChange, onClear }: Props) {
  const [text, setText] = useState(filters.q ?? '')

  // The address bar is the source of truth: keep the box in step when it changes underneath (Clear, Back).
  useEffect(() => setText(filters.q ?? ''), [filters.q])

  // Wait for a pause in typing before asking the server.
  useEffect(() => {
    if (text.trim() === (filters.q ?? '')) return
    const timer = window.setTimeout(() => onChange({ q: text.trim() || undefined }), 300)
    return () => window.clearTimeout(timer)
  }, [text, filters.q, onChange])

  return (
    <div className="filters" role="search" aria-label="Filter tasks">
      <Field label="Search titles">
        {(props) => (
          <input {...props} type="search" value={text} placeholder="Search" onChange={(e) => setText(e.target.value)} />
        )}
      </Field>
      <Field label="Assignee">
        {(props) => (
          <select {...props} value={filters.assignee ?? ''} onChange={(e) => onChange({ assignee: e.target.value || undefined })}>
            <option value="">Anyone</option>
            <option value="unassigned">Unassigned</option>
            {members.map((member) => (
              <option key={member.user.id} value={member.user.id}>
                {member.user.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Priority">
        {(props) => (
          <select
            {...props}
            value={filters.priority ?? ''}
            onChange={(e) => onChange({ priority: (e.target.value as Priority) || undefined })}
          >
            <option value="">Any</option>
            {[...PRIORITIES].reverse().map((priority) => (
              <option key={priority} value={priority}>
                {PRIORITY_LABEL[priority]}
              </option>
            ))}
          </select>
        )}
      </Field>
      {showStatus && (
        <Field label="Status">
          {(props) => (
            <select
              {...props}
              value={filters.status ?? ''}
              onChange={(e) => onChange({ status: (e.target.value as Status) || undefined })}
            >
              <option value="">Any</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABEL[status]}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
      {active && (
        <button type="button" className="btn small clear" onClick={onClear}>
          Clear filters
        </button>
      )}
    </div>
  )
}
