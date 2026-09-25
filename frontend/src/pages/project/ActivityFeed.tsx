import { Link } from 'react-router-dom'
import { useActivity } from '../../api/hooks'
import type { Activity } from '../../api/types'
import { useMe } from '../../auth/AuthProvider'
import { ErrorPanel, Loading } from '../../components/QueryState'
import { describe } from '../../lib/activity'
import { formatStamp, timeAgo } from '../../lib/format'

export function ActivityList({ items, showProject = false }: { items: Activity[]; showProject?: boolean }) {
  const me = useMe()
  return (
    <ol className="feed">
      {items.map((item) => (
        <li key={item.id}>
          <time dateTime={item.created_at} title={formatStamp(item.created_at)}>
            {timeAgo(item.created_at)}
          </time>
          <span>
            {showProject && item.project && (
              <Link className="feed-project" to={`/projects/${item.project.id}/board`}>
                {item.project.name}
              </Link>
            )}
            {describe(item.type, item.actor.id === me.id ? 'You' : item.actor.name, item.meta, me.id)}
          </span>
        </li>
      ))}
    </ol>
  )
}

/** Newest first, with "Show older" paging by cursor so events arriving live never shuffle the list. */
export function ProjectActivity({ projectId }: { projectId: string }) {
  const feed = useActivity(projectId)

  let body
  if (feed.isPending) body = <Loading label="activity" />
  else if (feed.isError) body = <ErrorPanel error={feed.error} onRetry={() => void feed.refetch()} busy={feed.isFetching} />
  else {
    const items = feed.data.pages.flatMap((page) => page.items)
    body =
      items.length === 0 ? (
        <p className="dim">Nothing has happened yet. Changes to tasks and members will show up here as they happen.</p>
      ) : (
        <>
          <ActivityList items={items} />
          {feed.hasNextPage && (
            <button
              type="button"
              className="btn small"
              onClick={() => void feed.fetchNextPage()}
              disabled={feed.isFetchingNextPage}
            >
              {feed.isFetchingNextPage ? 'Loading…' : 'Show older'}
            </button>
          )}
        </>
      )
  }

  return (
    <section className="panel activity" aria-labelledby="activity-title">
      <h2 id="activity-title">Activity</h2>
      {body}
    </section>
  )
}
