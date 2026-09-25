import { useId, type ReactNode } from 'react'
import { ApiError } from '../api/client'

interface InputProps {
  id: string
  'aria-invalid': boolean
  'aria-describedby'?: string
}

interface Props {
  label: string
  error?: string
  hint?: string
  children: (props: InputProps) => ReactNode
}

/** A labelled control with an inline error, wired up for screen readers. */
export function Field({ label, error, hint, children }: Props) {
  const id = useId()
  const messageId = `${id}-message`
  const message = error ?? hint
  return (
    <div className={`field${error ? ' has-error' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': message ? messageId : undefined })}
      {message && (
        <p id={messageId} className={error ? 'field-error' : 'field-hint'} role={error ? 'alert' : undefined}>
          {message}
        </p>
      )}
    </div>
  )
}

export type FormErrors = Record<string, string | undefined>

/** Server field errors go under their inputs; anything else becomes one message above the button. */
export function toErrors(err: unknown): FormErrors {
  if (err instanceof ApiError) return Object.keys(err.fields).length ? { ...err.fields } : { form: err.message }
  return { form: 'Something went wrong. Try again.' }
}

export function FormMessage({ text }: { text?: string }) {
  return text ? (
    <p className="form-error" role="alert">
      {text}
    </p>
  ) : null
}
