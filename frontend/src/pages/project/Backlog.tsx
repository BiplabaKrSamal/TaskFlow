import type { SortKey } from '../../api/hooks'
import { useTasks } from '../../api/hooks'
import { Pager, PriorityTag, Person, StatusTag } from '../../components/Bits'
import { QueryState } from '../../components/QueryState'
import { formatDay, isOverdue } from '../../lib/format'
import { useProjectContext } from './ProjectPage'

const SIZES = [10, 20, 50]
const SORTS: SortKey[] = ['priority', 'due_date', 'created_at']
const DEFAULT_ORDER: Record<SortKey, 'asc' | 'desc'> = { priority: 'desc', due_date: 'asc', created_at: 'desc' }

interface SortHeaderProps {
  label: string
  field: SortKey
  sort: SortKey
  order: 'asc' | 'desc'
  onSort: (field: SortKey, order: 'asc' | 'desc') => void
}

function SortHeader({ label, field, sort, order, onSort }: SortHeaderProps) {
  const active = sort === field
  const next = active ? (order === 'asc' ? 'desc' : 'asc') : DEFAULT_ORDER[field]
  return (
    <th aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="th-sort" onClick={() => onSort(field, next)}>
        {label}
        {active && <span aria-hidden="true">{order === 'asc' ? ' ↑' : ' ↓'}</span>}
      </button>
    </th>
  )
}

export function BacklogTab() {
  const { project, filters, filtersActive, clearFilters, params, update, openTask, newTask } = useProjectContext()

  const sortParam = params.get('sort') as SortKey | null
  const sort: SortKey = sortParam && SORTS.includes(sortParam) ? sortParam : 'created_at'
  const orderParam = params.get('order')
  const order = orderParam === 'asc' || orderParam === 'desc' ? orderParam : DEFAULT_ORDER[sort]
  const page = Math.max(1, Number.parseInt(params.get('page') ?? '1', 10) || 1)
  const sizeParam = Number.parseInt(params.get('size') ?? '', 10)
  const size = SIZES.includes(sizeParam) ? sizeParam : 20

  // Sorting, filtering and paging all happen in the database; this only ever holds one page.
  const tasks = useTasks(project.id, { ...filters, sort, order, page, page_size: size })

  const onSort = (field: SortKey, next: 'asc' | 'desc') => update({ sort: field, order: next })

  return (
    <QueryState
      query={tasks}
      label="tasks"
      isEmpty={(data) => data.items.length === 0}
      empty={
        <div className="state">
          {page > 1 ? (
            <>
              <p>There is nothing on this page any more.</p>
              <button type="button" className="btn" onClick={() => update({ page: undefined })}>
                Go to the first page
              </button>
            </>
          ) : filtersActive ? (
            <>
              <p>No tasks match these filters.</p>
              <button type="button" className="btn" onClick={clearFilters}>
                Clear filters
              </button>
            </>
          ) : (
            <>
              <p>No tasks yet.</p>
              <button type="button" className="btn primary" onClick={newTask}>
                New task
              </button>
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
                  <th>Title</th>
                  <th>Status</th>
                  <SortHeader label="Priority" field="priority" sort={sort} order={order} onSort={onSort} />
                  <th>Assignee</th>
                  <SortHeader label="Due" field="due_date" sort={sort} order={order} onSort={onSort} />
                  <SortHeader label="Created" field="created_at" sort={sort} order={order} onSort={onSort} />
                </tr>
              </thead>
              <tbody>
                {data.items.map((task) => (
                  <tr key={task.id} onClick={() => openTask(task.id)}>
                    <td>
                      <button
                        type="button"
                        className="linklike"
                        onClick={(event) => {
                          event.stopPropagation()
                          openTask(task.id)
                        }}
                      >
                        {task.title}
                      </button>
                    </td>
                    <td>
                      <StatusTag status={task.status} />
                    </td>
                    <td>
                      <PriorityTag priority={task.priority} />
                    </td>
                    <td>
                      <Person user={task.assignee} />
                    </td>
                    <td className={isOverdue(task.due_date, task.status) ? 'overdue' : undefined}>
                      {task.due_date ? formatDay(task.due_date) : <span className="dim">None</span>}
                    </td>
                    <td className="dim">{formatDay(task.created_at.slice(0, 10))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager-row">
            <Pager
              page={data.page}
              pages={data.pages}
              total={data.total}
              noun="task"
              busy={tasks.isPlaceholderData}
              onPage={(next) => update({ page: String(next) }, { keepPage: true })}
            />
            <label className="per-page">
              <span className="dim">Per page</span>
              <select value={size} onChange={(e) => update({ size: e.target.value })}>
                {SIZES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </>
      )}
    </QueryState>
  )
}
