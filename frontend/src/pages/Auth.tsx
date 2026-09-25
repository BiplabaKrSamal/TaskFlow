import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Field, FormMessage, toErrors, type FormErrors } from '../components/Field'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function AuthShell({ title, footer, children }: { title: string; footer: ReactNode; children: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-panel">
        <p className="wordmark large">taskflow</p>
        <h1>{title}</h1>
        {children}
        <p className="auth-alt">{footer}</p>
      </div>
    </div>
  )
}

function returnPath(state: unknown): string {
  return (state as { from?: string } | null)?.from ?? '/'
}

export function LoginPage() {
  const { login, status } = useAuth()
  const { state } = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})
  const [busy, setBusy] = useState(false)

  if (status === 'authed') return <Navigate to={returnPath(state)} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const problems: FormErrors = {}
    if (!EMAIL.test(email.trim())) problems.email = 'Enter a valid email address'
    if (!password) problems.password = 'Enter your password'
    setErrors(problems)
    if (Object.keys(problems).length) return

    setBusy(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setErrors(toErrors(err))
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      footer={
        <>
          New here? <Link to="/signup">Create an account</Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <Field label="Email" error={errors.email}>
          {(props) => (
            <input {...props} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Field>
        <Field label="Password" error={errors.password}>
          {(props) => (
            <input
              {...props}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <FormMessage text={errors.form} />
        <button type="submit" className="btn primary block" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthShell>
  )
}

function checkSignup(name: string, email: string, password: string): FormErrors {
  const problems: FormErrors = {}
  if (!name.trim()) problems.name = 'Name is required'
  if (!EMAIL.test(email.trim())) problems.email = 'Enter a valid email address'
  if (password.length < 8) problems.password = 'Password must be at least 8 characters'
  else if (!/\p{L}/u.test(password) || !/\d/.test(password))
    problems.password = 'Password must include at least one letter and one number'
  return problems
}

export function SignupPage() {
  const { signup, status } = useAuth()
  const { state } = useLocation()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})
  const [busy, setBusy] = useState(false)

  if (status === 'authed') return <Navigate to={returnPath(state)} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const problems = checkSignup(name, email, password)
    setErrors(problems)
    if (Object.keys(problems).length) return

    setBusy(true)
    try {
      await signup(name.trim(), email.trim(), password)
    } catch (err) {
      setErrors(toErrors(err))
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      footer={
        <>
          Already have one? <Link to="/login">Sign in</Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <Field label="Name" error={errors.name}>
          {(props) => <input {...props} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Email" error={errors.email}>
          {(props) => (
            <input {...props} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Field>
        <Field label="Password" error={errors.password} hint="At least 8 characters, with a letter and a number.">
          {(props) => (
            <input
              {...props}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <FormMessage text={errors.form} />
        <button type="submit" className="btn primary block" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
