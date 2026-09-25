import { Link, useSearchParams } from 'react-router-dom'
import { useMyTasks } from '../api/hooks'
import type { Status } from '../api/types'
import { Pager, PriorityTag, StatusTag } from '../components/Bits'
import { Field } from '../components/Field'
import { QueryState } from '../components/QueryState'
import { STATUSES, STATUS_LABEL, formatDay, isOverdue } from '../lib/format'

export function AssignedPage() {
  const [params, setParams] = useSearchParams()
  const statusParam = params.get('status') as Status | null
  const status = statusParam && STATUSES.includes(statusParam) ? statusParam : undefined
  const page = Math.max(1, Number.parseInt(params.get('page') ?? '1', 10) || 1)
  const tasks = useMyTasks({ status, page, page_size: 20 })

  function change(next: { status?: string; page?: number }) {
    const updated = new URLSearchParams(params)
    if ('status' in next) {
      if (next.status) updated.set('status', next.status)
      else updated.delete('status')
      updated.delete('page')
    }
    if (next.page !== undefined) updated.set('page', String(next.page))
    setParams(updated, { replace: true })
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>Assigned to me</h1>
        <div className="head-filter">
          <Field label="Status">
            {(props) => (
              <select {...props} value={status ?? ''} onChange={(e) => change({ status: e.target.value })}>
                <option value="">Any</option>
                {STATUSES.map((option) => (
                  <option key={option} value={option}>
                    {STATUS_LABEL[option]}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
      </div>

      <QueryState
        query={tasks}
        label="your tasks"
        isEmpty={(data) => data.items.length === 0}
        empty={
          <div className="state">
            {status ? (
              <p>Nothing assigned to you is {STATUS_LABEL[status]}.</p>
            ) : (
              <>
                <p>Nothing is assigned to you.</p>
                <p className="dim">When someone assigns you a task it shows up here, whichever project it is in.</p>
              </>
            )}
          </div>
        }
      >
        {(data) => (
          <>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Project</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Due</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((task) => (
                    <tr key={task.id}>
                      <td>
                        <Link className="linklike" to={`/projects/${task.project.id}/board?task=${task.id}`}>
                          {task.title}
                        </Link>
                      </td>
                      <td className="dim">{task.project.name}</td>
                      <td>
                        <StatusTag status={task.status} />
                      </td>
                      <td>
                        <PriorityTag priority={task.priority} />
                      </td>
                      <td className={isOverdue(task.due_date, task.status) ? 'overdue' : undefined}>
                        {task.due_date ? formatDay(task.due_date) : <span className="dim">None</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager
              page={data.page}
              pages={data.pages}
              total={data.total}
              noun="task"
              busy={tasks.isPlaceholderData}
              onPage={(next) => change({ page: next })}
            />
          </>
        )}
      </QueryState>
    </div>
  )
}
