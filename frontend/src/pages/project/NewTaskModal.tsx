import { useState, type FormEvent } from 'react'
import { useCreateTask } from '../../api/hooks'
import type { Priority, ProjectDetail } from '../../api/types'
import { Field, FormMessage, toErrors, type FormErrors } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { PRIORITIES, PRIORITY_LABEL, todayUtc } from '../../lib/format'

export function NewTaskModal({ project, onClose }: { project: ProjectDetail; onClose: () => void }) {
  const create = useCreateTask(project.id)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [due, setDue] = useState('')
  const [assignee, setAssignee] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})

  function submit(event: FormEvent) {
    event.preventDefault()
    if (create.isPending) return
    const problems: FormErrors = {}
    if (!title.trim()) problems.title = 'Title cannot be empty'
    if (due && due < todayUtc()) problems.due_date = 'Due date cannot be in the past'
    setErrors(problems)
    if (Object.keys(problems).length) return

    create.mutate(
      { title, description, priority, due_date: due || null, assignee_id: assignee || null },
      { onSuccess: onClose, onError: (err) => setErrors(toErrors(err)) },
    )
  }

  return (
    <Modal title="New task" onClose={onClose}>
      <form onSubmit={submit} noValidate className="task-form">
        <Field label="Title" error={errors.title}>
          {(props) => <input {...props} value={title} maxLength={200} autoFocus onChange={(e) => setTitle(e.target.value)} />}
        </Field>
        <Field label="Description" error={errors.description}>
          {(props) => <textarea {...props} rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <div className="form-grid">
          <Field label="Priority" error={errors.priority}>
            {(props) => (
              <select {...props} value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
                {PRIORITIES.map((option) => (
                  <option key={option} value={option}>
                    {PRIORITY_LABEL[option]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Assignee" error={errors.assignee_id}>
            {(props) => (
              <select {...props} value={assignee} onChange={(e) => setAssignee(e.target.value)}>
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
            {(props) => <input {...props} type="date" min={todayUtc()} value={due} onChange={(e) => setDue(e.target.value)} />}
          </Field>
        </div>
        <FormMessage text={errors.form} />
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create task'}
          </button>
          <button type="button" className="btn" onClick={onClose} disabled={create.isPending}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}
