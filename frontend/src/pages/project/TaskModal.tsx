import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { useAddComment, useComments, useDeleteTask, useTask, useUpdateTask, type TaskPatch } from '../../api/hooks'
import type { Priority, ProjectDetail, Status, Task } from '../../api/types'
import { Person } from '../../components/Bits'
import { Field, FormMessage, toErrors, type FormErrors } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { QueryState } from '../../components/QueryState'
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL, formatStamp, timeAgo, todayUtc } from '../../lib/format'

/** Only what the person actually touched. Everything else keeps showing the server's latest value. */
interface Draft {
  title?: string
  description?: string
  status?: Status
  priority?: Priority
  due?: string // '' means no due date
  assignee?: string // '' means unassigned
}

const ERROR_KEY: Record<keyof Draft, string> = {
  title: 'title',
  description: 'description',
  status: 'status',
  priority: 'priority',
  due: 'due_date',
  assignee: 'assignee_id',
}

function buildPatch(task: Task, draft: Draft): TaskPatch {
  const patch: TaskPatch = {}
  if (draft.title !== undefined && draft.title.trim() !== task.title) patch.title = draft.title
  if (draft.description !== undefined && draft.description.trim() !== task.description) patch.description = draft.description
  if (draft.status !== undefined && draft.status !== task.status) patch.status = draft.status
  if (draft.priority !== undefined && draft.priority !== task.priority) patch.priority = draft.priority
  if (draft.due !== undefined && (draft.due || null) !== task.due_date) patch.due_date = draft.due || null
  if (draft.assignee !== undefined && (draft.assignee || null) !== task.assignee_id) patch.assignee_id = draft.assignee || null
  return patch
}

function Comments({ projectId, taskId }: { projectId: string; taskId: string }) {
  const comments = useComments(projectId, taskId)
  const add = useAddComment(projectId, taskId)
  const [body, setBody] = useState('')
  const [error, setError] = useState<string>()

  function post(event: FormEvent) {
    event.preventDefault()
    if (add.isPending) return
    if (!body.trim()) {
      setError('Comment cannot be empty')
      return
    }
    setError(undefined)
    add.mutate(body, {
      onSuccess: () => setBody(''),
      onError: (err) => {
        const problems = toErrors(err)
        setError(problems.body ?? problems.form)
      },
    })
  }

  return (
    <section className="comments-section" aria-labelledby="comments-title">
      <h3 id="comments-title">Comments</h3>
      <QueryState
        query={comments}
        label="comments"
        isEmpty={(list) => list.length === 0}
        empty={<p className="dim">No comments yet. Start the conversation.</p>}
      >
        {(list) => (
          <ol className="comments">
            {list.map((comment) => (
              <li key={comment.id}>
                <header>
                  <strong>{comment.author.name}</strong>
                  <time dateTime={comment.created_at} title={formatStamp(comment.created_at)}>
                    {timeAgo(comment.created_at)}
                  </time>
                </header>
                <p>{comment.body}</p>
              </li>
            ))}
          </ol>
        )}
      </QueryState>
      <form onSubmit={post} noValidate className="comment-form">
        <Field label="Add a comment" error={error}>
          {(props) => <textarea {...props} rows={3} value={body} onChange={(e) => setBody(e.target.value)} maxLength={2000} />}
        </Field>
        <button type="submit" className="btn" disabled={add.isPending || !body.trim()}>
          {add.isPending ? 'Posting…' : 'Post comment'}
        </button>
      </form>
    </section>
  )
}

function TaskEditor({ task, project, onClose }: { task: Task; project: ProjectDetail; onClose: () => void }) {
  const update = useUpdateTask(project.id)
  const remove = useDeleteTask(project.id)
  const [draft, setDraft] = useState<Draft>({})
  const [errors, setErrors] = useState<FormErrors>({})
  const [saved, setSaved] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const patch = buildPatch(task, draft)
  const dirty = Object.keys(patch).length > 0

  function change<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
    setSaved(false)
    setErrors((current) => ({ ...current, [ERROR_KEY[key]]: undefined, form: undefined }))
  }

  function save(event: FormEvent) {
    event.preventDefault()
    if (update.isPending || !dirty) return
    const problems: FormErrors = {}
    if (patch.title !== undefined && !patch.title.trim()) problems.title = 'Title cannot be empty'
    if (patch.due_date && patch.due_date < todayUtc()) problems.due_date = 'Due date cannot be in the past'
    setErrors(problems)
    if (Object.keys(problems).length) return

    update.mutate(
      { taskId: task.id, patch },
      {
        onSuccess: () => {
          setDraft({})
          setSaved(true)
        },
        onError: (err) => setErrors(toErrors(err)),
      },
    )
  }

  return (
    <>
      <form onSubmit={save} noValidate className="task-form">
        <Field label="Title" error={errors.title}>
          {(props) => (
            <input {...props} value={draft.title ?? task.title} maxLength={200} onChange={(e) => change('title', e.target.value)} />
          )}
        </Field>
        <Field label="Description" error={errors.description}>
          {(props) => (
            <textarea
              {...props}
              rows={4}
              value={draft.description ?? task.description}
              onChange={(e) => change('description', e.target.value)}
            />
          )}
        </Field>
        <div className="form-grid">
          <Field label="Status" error={errors.status}>
            {(props) => (
              <select {...props} value={draft.status ?? task.status} onChange={(e) => change('status', e.target.value as Status)}>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {STATUS_LABEL[status]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Priority" error={errors.priority}>
            {(props) => (
              <select
                {...props}
                value={draft.priority ?? task.priority}
                onChange={(e) => change('priority', e.target.value as Priority)}
              >
                {PRIORITIES.map((priority) => (
                  <option key={priority} value={priority}>
                    {PRIORITY_LABEL[priority]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Assignee" error={errors.assignee_id}>
            {(props) => (
              <select
                {...props}
                value={draft.assignee ?? task.assignee_id ?? ''}
                onChange={(e) => change('assignee', e.target.value)}
              >
                <option value="">Unassigned</option>
                {project.members.map((member) => (
                  <option key={member.user.id} value={member.user.id}>
                    {member.user.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Due date" error={errors.due_date}>
            {(props) => (
              <input
                {...props}
                type="date"
                value={draft.due ?? task.due_date ?? ''}
                onChange={(e) => change('due', e.target.value)}
              />
            )}
          </Field>
        </div>

        <FormMessage text={errors.form} />
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={!dirty || update.isPending}>
            {update.isPending ? 'Saving…' : 'Save changes'}
          </button>
          {saved && !dirty && (
            <span className="form-ok" role="status">
              Saved
            </span>
          )}
          <span className="spacer" />
          {confirmingDelete ? (
            <>
              <button
                type="button"
                className="btn danger"
                disabled={remove.isPending}
                onClick={() =>
                  remove.mutate(task.id, { onSuccess: onClose, onError: (err) => setErrors(toErrors(err)) })
                }
              >
                {remove.isPending ? 'Deleting…' : 'Delete permanently'}
              </button>
              <button type="button" className="btn" disabled={remove.isPending} onClick={() => setConfirmingDelete(false)}>
                Keep task
              </button>
            </>
          ) : (
            <button type="button" className="btn danger" onClick={() => setConfirmingDelete(true)}>
              Delete task
            </button>
          )}
        </div>
      </form>

      <dl className="task-facts">
        <div>
          <dt>Created by</dt>
          <dd>
            <Person user={task.creator} /> on {formatStamp(task.created_at)}
          </dd>
        </div>
        {task.completed_at && (
          <div>
            <dt>Completed</dt>
            <dd>{formatStamp(task.completed_at)}</dd>
          </div>
        )}
      </dl>

      <Comments projectId={project.id} taskId={task.id} />
    </>
  )
}

interface Props {
  project: ProjectDetail
  taskId: string
  onClose: () => void
}

export function TaskModal({ project, taskId, onClose }: Props) {
  const task = useTask(project.id, taskId)
  const gone = task.error instanceof ApiError && task.error.status === 404

  return (
    <Modal title="Task details" onClose={onClose}>
      {gone ? (
        <div className="state">
          <p>This task no longer exists. Someone may have deleted it.</p>
        </div>
      ) : (
        <QueryState query={task} label="task">
          {(current) => <TaskEditor key={current.id} task={current} project={project} onClose={onClose} />}
        </QueryState>
      )}
    </Modal>
  )
}
