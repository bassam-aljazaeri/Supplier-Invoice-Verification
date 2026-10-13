import type { HTMLInputTypeAttribute } from 'react'
import type { ApiFailure } from '../api.ts'
import type { ErrorDetail } from '../types.ts'
import { fieldError } from '../validation.ts'

export function TextField({ id, field, label, value, onChange, details, hint, type = 'text', multiline = false, decimal = false }: {
  id: string; field: string; label: string; value: string; onChange: (value: string) => void
  details: ErrorDetail[]; hint?: string; type?: HTMLInputTypeAttribute; multiline?: boolean; decimal?: boolean
}) {
  const error = fieldError(details, field)
  const shared = { id, name: field, 'data-field': field, value, 'aria-invalid': !!error,
    'aria-describedby': [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined }
  return <div className="form-field">
    <label htmlFor={id}>{label}</label>
    {multiline ? <textarea {...shared} rows={4} onChange={(event) => onChange(event.target.value)} /> : <input {...shared} type={type} inputMode={decimal ? 'decimal' : undefined} onChange={(event) => onChange(event.target.value)} />}
    {hint && <p className="hint" id={`${id}-hint`}>{hint}</p>}
    {error && <p className="field-error" id={`${id}-error`}>{error}</p>}
  </div>
}

export function FormFeedback({ error, listHref }: { error: ApiFailure | null; listHref: string }) {
  if (!error) return null
  return <div className="error-summary" role="alert" tabIndex={-1}>
    <h3>{error.kind === 'validation' ? 'Check the form' : error.kind === 'conflict' ? 'Identifier already exists' : error.kind === 'missing' ? 'Reference not found' : 'Save could not be confirmed'}</h3>
    <p>{error.message}</p>
    {error.details.length > 0 && <ul>{error.details.map((detail, index) => <li key={`${detail.field}-${index}`}>{detail.message}</li>)}</ul>}
    {error.uncertainWrite && <p>The record may already have been saved. Your input is retained. Check the list for its code or number before trying Save again.</p>}
    {(error.uncertainWrite || error.kind === 'conflict') && <a href={listHref} target="_blank" rel="noopener noreferrer">Check saved records (opens a new tab)</a>}
    {(error.kind === 'unavailable' || error.kind === 'server' || error.kind === 'network' || error.kind === 'timeout') && <p><a href="#/status">Check service status</a></p>}
  </div>
}

export function SelectField({ id, field, label, value, onChange, details, options, disabled = false, hint }: {
  id: string; field: string; label: string; value: string; onChange: (value: string) => void
  details: ErrorDetail[]; options: { value: string; label: string }[]; disabled?: boolean; hint?: string
}) {
  const error = fieldError(details, field)
  return <div className="form-field"><label htmlFor={id}>{label}</label>
    <select id={id} name={field} data-field={field} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} aria-invalid={!!error} aria-describedby={[hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined}>
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
    {hint && <p className="hint" id={`${id}-hint`}>{hint}</p>}
    {error && <p className="field-error" id={`${id}-error`}>{error}</p>}
  </div>
}
