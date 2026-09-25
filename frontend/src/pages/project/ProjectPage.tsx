import { useCallback, useMemo, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { useProject, type TaskFilters } from '../../api/hooks'
import type { Priority, ProjectDetail, Status } from '../../api/types'
import { RoleTag } from '../../components/Bits'
import { QueryState } from '../../components/QueryState'
import { PRIORITIES, STATUSES } from '../../lib/format'
import { ProjectActivity } from './ActivityFeed'
import { FilterBar } from './FilterBar'
import { NewTaskModal } from './NewTaskModal'
import { TaskModal } from './TaskModal'

/** What the board, backlog and members tabs get from the page around them. */
export interface ProjectContext {
  project: ProjectDetail
  filters: TaskFilters
  filtersActive: boolean
  params: URLSearchParams
  update: (patch: Record<string, string | undefined>, options?: { keepPage?: boolean }) => void
  clearFilters: () => void
  openTask: (id: string) => void
  newTask: () => void
}

export function useProjectContext(): ProjectContext {
  return useOutletContext<ProjectContext>()
}

function readFilters(params: URLSearchParams): TaskFilters {
  const priority = params.get('priority') as Priority | null
  const status = params.get('status') as Status | null
  return {
    assignee: params.get('assignee') || undefined,
    priority: priority && PRIORITIES.includes(priority) ? priority : undefined,
    status: status && STATUSES.includes(status) ? status : undefined,
    q: params.get('q') || undefined,
  }
}

function ProjectView({ project }: { project: ProjectDetail }) {
  const [params, setParams] = useSearchParams()
  const { pathname } = useLocation()
  const [creating, setCreating] = useState(false)
  const onMembers = pathname.endsWith('/members')
  const onBacklog = pathname.endsWith('/backlog')

  // Filters, sorting, paging and the open task all live in the address bar:
  // a view can be shared, bookmarked and survives a reload.
  const latest = useRef(params)
  latest.current = params
  const update = useCallback<ProjectContext['update']>(
    (patch, options) => {
      const next = new URLSearchParams(latest.current)
      for (const [key, value] of Object.entries(patch)) {
        if (value) next.set(key, value)
        else next.delete(key)
      }
      if (!options?.keepPage) next.delete('page')
      setParams(next, { replace: true })
    },
    [setParams],
  )

  const filters = useMemo(() => readFilters(params), [params])
  const filtersActive = Boolean(filters.assignee || filters.priority || filters.q || filters.status)
  const clearFilters = useCallback(
    () => update({ assignee: undefined, priority: undefined, q: undefined, status: undefined }),
    [update],
  )
  const openTask = useCallback((id: string) => update({ task: id }, { keepPage: true }), [update])
  const taskId = params.get('task')

  const carried = new URLSearchParams()
  for (const key of ['assignee', 'priority', 'q']) {
    const value = params.get(key)
    if (value) carried.set(key, value)
  }
  const tabSearch = carried.toString()

  const context: ProjectContext = {
    project,
    filters,
    filtersActive,
    params,
    update,
    clearFilters,
    openTask,
    newTask: () => setCreating(true),
  }

  return (
    <>
      <header className="project-head">
        <div>
          <h1>{project.name}</h1>
          {project.description && <p className="dim lead">{project.description}</p>}
        </div>
        <div className="head-actions">
          <RoleTag role={project.role} />
          <button type="button" className="btn primary" onClick={() => setCreating(true)}>
            New task
          </button>
        </div>
      </header>

      <nav className="tabs" aria-label="Project views">
        <NavLink to={{ pathname: 'board', search: tabSearch }}>Board</NavLink>
        <NavLink to={{ pathname: 'backlog', search: tabSearch }}>Backlog</NavLink>
        <NavLink to="members">Members</NavLink>
      </nav>

      <div className="project-grid">
        <section aria-label="Tasks">
          {!onMembers && (
            <FilterBar
              members={project.members}
              filters={filters}
              showStatus={onBacklog}
              active={filtersActive}
              onChange={update}
              onClear={clearFilters}
            />
          )}
          <Outlet context={context} />
        </section>
        <aside>
          <ProjectActivity projectId={project.id} />
        </aside>
      </div>

      {taskId && <TaskModal project={project} taskId={taskId} onClose={() => update({ task: undefined }, { keepPage: true })} />}
      {creating && <NewTaskModal project={project} onClose={() => setCreating(false)} />}
    </>
  )
}

export function ProjectPage() {
  const { projectId = '' } = useParams()
  const project = useProject(projectId)

  if (project.error instanceof ApiError && project.error.status === 404) {
    return (
      <div className="page">
        <div className="state">
          <p>This project does not exist, or you no longer have access to it.</p>
          <Link className="btn" to="/">
            Back to projects
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <QueryState query={project} label="project">
        {(data) => <ProjectView project={data} />}
      </QueryState>
    </div>
  )
}
