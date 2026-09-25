import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDeleteProject, useInvite, useRemoveMember } from '../../api/hooks'
import type { Member, ProjectDetail } from '../../api/types'
import { useMe } from '../../auth/AuthProvider'
import { RoleTag } from '../../components/Bits'
import { Field, FormMessage, toErrors, type FormErrors } from '../../components/Field'
import { useToast } from '../../components/Toasts'
import { formatDay } from '../../lib/format'
import { useProjectContext } from './ProjectPage'

function MemberRow({ member, projectId, canRemove }: { member: Member; projectId: string; canRemove: boolean }) {
  const remove = useRemoveMember(projectId)
  const toast = useToast()
  const [confirming, setConfirming] = useState(false)
  const me = useMe()

  return (
    <li className="member">
      <span className="row-main">
        <strong>{member.user.name}</strong>
        {member.user.id === me.id && <span className="dim"> (you)</span>}
        <span className="dim">{member.user.email}</span>
      </span>
      <RoleTag role={member.role} />
      <span className="dim num">Joined {formatDay(member.joined_at.slice(0, 10))}</span>
      {canRemove && member.role !== 'owner' && (
        <span className="member-actions">
          {confirming ? (
            <>
              <button
                type="button"
                className="btn small danger"
                disabled={remove.isPending}
                onClick={() =>
                  remove.mutate(member.user.id, {
                    onSuccess: () => toast.info(`${member.user.name} was removed. Their tasks stay; what was assigned to them is now unassigned.`),
                    onError: (err) => toast.error(err.message),
                  })
                }
              >
                {remove.isPending ? 'Removing…' : `Remove ${member.user.name}`}
              </button>
              <button type="button" className="btn small" disabled={remove.isPending} onClick={() => setConfirming(false)}>
                Keep
              </button>
            </>
          ) : (
            <button type="button" className="btn small" onClick={() => setConfirming(true)}>
              Remove
            </button>
          )}
        </span>
      )}
    </li>
  )
}

function InviteForm({ projectId }: { projectId: string }) {
  const invite = useInvite(projectId)
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})
  const [invited, setInvited] = useState<string | null>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (invite.isPending) return
    setInvited(null)
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErrors({ email: 'Enter a valid email address' })
      return
    }
    setErrors({})
    invite.mutate(email.trim(), {
      onSuccess: () => {
        setInvited(email.trim())
        setEmail('')
      },
      onError: (err) => setErrors(toErrors(err)),
    })
  }

  return (
    <form className="panel invite" onSubmit={submit} noValidate>
      <h2>Invite someone</h2>
      <p className="dim">They need an account already. They join as a member straight away.</p>
      <div className="invite-row">
        <Field label="Email address" error={errors.email}>
          {(props) => <input {...props} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <button type="submit" className="btn primary" disabled={invite.isPending}>
          {invite.isPending ? 'Inviting…' : 'Invite'}
        </button>
      </div>
      <FormMessage text={errors.form} />
      {invited && (
        <p className="form-ok" role="status">
          {invited} is now a member.
        </p>
      )}
    </form>
  )
}

function DeleteProject({ project }: { project: ProjectDetail }) {
  const remove = useDeleteProject(project.id)
  const navigate = useNavigate()
  const toast = useToast()
  const [confirming, setConfirming] = useState(false)

  return (
    <section className="panel danger-zone">
      <h2>Delete this project</h2>
      <p className="dim">
        This permanently deletes the project with all of its tasks, comments and activity, for everyone in it.
      </p>
      {confirming ? (
        <div className="confirm-row">
          <button
            type="button"
            className="btn danger"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(undefined, {
                onSuccess: () => {
                  toast.info(`“${project.name}” was deleted`)
                  navigate('/')
                },
                onError: (err) => toast.error(err.message),
              })
            }
          >
            {remove.isPending ? 'Deleting…' : 'Delete permanently'}
          </button>
          <button type="button" className="btn" disabled={remove.isPending} onClick={() => setConfirming(false)}>
            Keep project
          </button>
        </div>
      ) : (
        <button type="button" className="btn danger" onClick={() => setConfirming(true)}>
          Delete project
        </button>
      )}
    </section>
  )
}

export function MembersTab() {
  const { project } = useProjectContext()
  const isOwner = project.role === 'owner'
  return (
    <div className="stack">
      <section className="panel">
        <h2>
          Members <span className="count">{project.members.length}</span>
        </h2>
        <ul className="members">
          {project.members.map((member) => (
            <MemberRow key={member.user.id} member={member} projectId={project.id} canRemove={isOwner} />
          ))}
        </ul>
      </section>
      {isOwner && <InviteForm projectId={project.id} />}
      {isOwner && <DeleteProject project={project} />}
    </div>
  )
}
