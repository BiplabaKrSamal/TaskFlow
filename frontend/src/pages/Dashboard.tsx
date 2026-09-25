import { Link } from 'react-router-dom'
import { useDashboard } from '../api/hooks'
import type { Dashboard } from '../api/types'
import { QueryState } from '../components/QueryState'
import { STATUSES, STATUS_LABEL } from '../lib/format'
import { ActivityList } from './project/ActivityFeed'

function Readout({ data }: { data: Dashboard }) {
  return (
    <>
      <div className="tiles">
        <section className="tile">
          <h2>Projects</h2>
          <p className="reading amber">{data.project_count}</p>
        </section>
        <section className="tile wide">
          <h2>Assigned to me</h2>
          <dl className="split">
            {STATUSES.map((status) => (
              <div key={status}>
                <dt>{STATUS_LABEL[status]}</dt>
                <dd className={status === 'in_progress' ? 'cyan' : status === 'todo' ? 'amber' : undefined}>
                  {data.assigned[status]}
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="tile">
          <h2>Completed this week</h2>
          <p className="reading cyan">{data.completed_this_week}</p>
        </section>
        <section className="tile">
          <h2>Project with the most open tasks</h2>
          {data.busiest_project ? (
            <>
              <Link className="tile-link" to={`/projects/${data.busiest_project.id}/board`}>
                {data.busiest_project.name}
              </Link>
              <p className="dim">{data.busiest_project.open_tasks} open</p>
            </>
          ) : (
            <p className="dim">No open tasks in any of your projects.</p>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>My recent activity</h2>
        {data.recent_activity.length === 0 ? (
          <p className="dim">Nothing yet. What you do, and what happens to your tasks, shows up here.</p>
        ) : (
          <ActivityList items={data.recent_activity} showProject />
        )}
      </section>
    </>
  )
}

export function DashboardPage() {
  const dashboard = useDashboard()
  return (
    <div className="page">
      <div className="page-head">
        <h1>Dashboard</h1>
      </div>
      <QueryState query={dashboard} label="dashboard">
        {(data) => <Readout data={data} />}
      </QueryState>
    </div>
  )
}
