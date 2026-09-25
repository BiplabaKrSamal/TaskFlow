import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useCreateProject, useProjects } from '../api/hooks'
import { Field, FormMessage, toErrors, type FormErrors } from '../components/Field'
import { QueryState } from '../components/QueryState'
import { RoleTag } from '../components/Bits'

function NewProject() {
  const create = useCreateProject()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})

  function submit(event: FormEvent) {
    event.preventDefault()
    if (create.isPending) return
    if (!name.trim()) {
      setErrors({ name: 'Project name is required' })
      return
    }
    setErrors({})
    create.mutate(
      { name, description },
      {
        onSuccess: () => {
          setName('')
          setDescription('')
        },
        onError: (err) => setErrors(toErrors(err)),
      },
    )
  }

  return (
    <form className="panel new-project" onSubmit={submit} noValidate>
      <Field label="Project name" error={errors.name}>
        {(props) => <input {...props} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />}
      </Field>
      <Field label="Description" error={errors.description}>
        {(props) => <input {...props} value={description} onChange={(e) => setDescription(e.target.value)} />}
      </Field>
      <button type="submit" className="btn primary" disabled={create.isPending}>
        {create.isPending ? 'Creating…' : 'Create project'}
      </button>
      <FormMessage text={errors.form} />
    </form>
  )
}

export function ProjectsPage() {
  const projects = useProjects()
  return (
    <div className="page">
      <div className="page-head">
        <h1>Projects</h1>
      </div>
      <NewProject />
      <QueryState
        query={projects}
        label="projects"
        isEmpty={(list) => list.length === 0}
        empty={
          <div className="state">
            <p>You are not in any project yet.</p>
            <p className="dim">Name one above to start a board, or ask a teammate to invite you to theirs.</p>
          </div>
        }
      >
        {(list) => (
          <ul className="rows">
            {list.map((project) => (
              <li key={project.id}>
                <Link className="row" to={`/projects/${project.id}`}>
                  <span className="row-main">
                    <strong>{project.name}</strong>
                    {project.description && <span className="dim clamp">{project.description}</span>}
                  </span>
                  <RoleTag role={project.role} />
                  <span className="num">
                    {project.member_count} {project.member_count === 1 ? 'member' : 'members'}
                  </span>
                  <span className="num">{project.open_task_count} open</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </div>
  )
}
