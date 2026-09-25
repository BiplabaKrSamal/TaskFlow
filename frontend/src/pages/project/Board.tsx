import { ApiError } from '../../api/client'
import { useBoard, useUpdateTask } from '../../api/hooks'
import type { Status, Task } from '../../api/types'
import { QueryState } from '../../components/QueryState'
import { useToast } from '../../components/Toasts'
import { STATUSES, STATUS_LABEL } from '../../lib/format'
import { TaskCard } from './TaskCard'
import { useProjectContext } from './ProjectPage'

export function BoardTab() {
  const { project, filters, filtersActive, clearFilters, openTask, newTask } = useProjectContext()
  const board = useBoard(project.id, filters)
  const move = useUpdateTask(project.id)
  const toast = useToast()

  function moveTo(task: Task, status: Status) {
    move.mutate(
      { taskId: task.id, patch: { status } },
      {
        // The server decides who may finish a task, and says why when it refuses.
        onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Could not move that task. Try again.'),
      },
    )
  }
  const movingId = move.isPending ? move.variables?.taskId : undefined
  const movingTo = move.isPending ? move.variables?.patch.status : undefined

  return (
    <QueryState query={board} label="board">
      {(data) => {
        const total = STATUSES.reduce((sum, status) => sum + data.columns[status].length, 0)
        if (total === 0) {
          return filtersActive ? (
            <div className="state">
              <p>No tasks match these filters.</p>
              <button type="button" className="btn" onClick={clearFilters}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className="state">
              <p>No tasks yet.</p>
              <p className="dim">Create the first one and everyone in the project sees it appear.</p>
              <button type="button" className="btn primary" onClick={newTask}>
                New task
              </button>
            </div>
          )
        }
        return (
          <div className="board">
            {STATUSES.map((status) => (
              <section key={status} className="column" aria-labelledby={`column-${status}`}>
                <header>
                  <h2 id={`column-${status}`}>{STATUS_LABEL[status]}</h2>
                  <span className="count">{data.columns[status].length}</span>
                </header>
                <div className="column-body">
                  {data.columns[status].length === 0 ? (
                    <p className="column-empty">Empty</p>
                  ) : (
                    data.columns[status].map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        movingTo={movingId === task.id ? movingTo : undefined}
                        onOpen={openTask}
                        onMove={moveTo}
                      />
                    ))
                  )}
                </div>
              </section>
            ))}
          </div>
        )
      }}
    </QueryState>
  )
}
