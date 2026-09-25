import type { Status, Task } from '../../api/types'
import { PriorityTag, Person } from '../../components/Bits'
import { formatDay, isOverdue } from '../../lib/format'

const ACTIONS: Record<Status, { label: string; busy: string; to: Status }[]> = {
  todo: [
    { label: 'Start', busy: 'Starting…', to: 'in_progress' },
    { label: 'Mark done', busy: 'Marking done…', to: 'done' },
  ],
  in_progress: [
    { label: 'Back to To Do', busy: 'Moving…', to: 'todo' },
    { label: 'Mark done', busy: 'Marking done…', to: 'done' },
  ],
  done: [{ label: 'Reopen', busy: 'Reopening…', to: 'in_progress' }],
}

interface Props {
  task: Task
  /** The status this card is currently being moved to, if a move is in flight. */
  movingTo?: Status
  onOpen: (id: string) => void
  onMove: (task: Task, to: Status) => void
}

export function TaskCard({ task, movingTo, onOpen, onMove }: Props) {
  const moving = movingTo !== undefined
  return (
    <article className={`card priority-${task.priority}${moving ? ' is-pending' : ''}`} aria-busy={moving}>
      <button type="button" className="card-title" onClick={() => onOpen(task.id)}>
        {task.title}
      </button>
      <div className="card-meta">
        <PriorityTag priority={task.priority} />
        {task.due_date && (
          <span className={isOverdue(task.due_date, task.status) ? 'due overdue' : 'due'}>Due {formatDay(task.due_date)}</span>
        )}
        {task.comment_count > 0 && (
          <span className="dim">
            {task.comment_count} {task.comment_count === 1 ? 'comment' : 'comments'}
          </span>
        )}
      </div>
      <div className="card-foot">
        <Person user={task.assignee} />
        <span className="card-actions">
          {ACTIONS[task.status].map((action) => (
            <button key={action.to} type="button" className="btn small" disabled={moving} onClick={() => onMove(task, action.to)}>
              {movingTo === action.to ? action.busy : action.label}
            </button>
          ))}
        </span>
      </div>
    </article>
  )
}
