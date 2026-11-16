import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useCanCreate } from '../../authContext.tsx'
import { createUploadFlow } from '../../documentUpload.ts'
import { navigate, subscribeHashChange } from '../../navigation.ts'

export default function DocumentUploadPage() {
  const canUpload = useCanCreate()
  const [flow] = useState(() => createUploadFlow())
  const state = useSyncExternalStore(flow.subscribe, flow.snapshot, flow.snapshot)
  const [clock, setClock] = useState(Date.now)
  const input = useRef<HTMLInputElement>(null), summary = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = input.current
    flow.activate()
    const clear = () => { flow.dispose(); if (element) element.value = '' }
    const unsubscribe = subscribeHashChange(clear)
    return () => { clear(); unsubscribe() }
  }, [flow])
  useEffect(() => { if (state.error) summary.current?.focus() }, [state.error])
  useEffect(() => {
    if (!state.uncertain || state.replayAfter <= clock) return
    const timer = setTimeout(() => setClock(Date.now()), state.replayAfter - Date.now() + 10)
    return () => clearTimeout(timer)
  }, [state.uncertain, state.replayAfter, clock])
  const saved = (record: { id: string }) => navigate(`#/documents/${record.id}`)
  if (!canUpload) return <section className="business-panel"><h2>Read-only document access</h2><p>Approvers can read metadata and download accepted documents. An administrator or accountant can upload.</p><a href="#/documents">Back to documents</a></section>
  return <section className="business-panel"><div className="panel-heading"><h2>Upload document</h2><a href="#/documents">Back to documents</a></div>
    <p>Use one fictional PDF, JPEG or PNG file, at most 5,000,000 bytes. PDFs must have exactly one page and no password. Images must be single-frame, at most 10,000,000 pixels and 10,000 pixels per dimension.</p>
    <p>Browser checks are early feedback. The server makes the final decision. Uploading does not create an invoice.</p>
    <form noValidate aria-busy={state.pending} onSubmit={(event) => { event.preventDefault(); void flow.submit(saved) }}>
      {state.error && <div className="error-summary" role="alert" tabIndex={-1} ref={summary}><h3>Upload could not be confirmed</h3><p>{state.error.message}</p>{state.error.details.length > 0 && <ul>{state.error.details.map((detail, index) => <li key={index}>{detail.message}</li>)}</ul>}<a href="#/status">Check service status</a></div>}
      <div className="form-field"><label htmlFor="document-file">Fictional invoice file</label>
        <input ref={input} id="document-file" name="file" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" disabled={state.pending || state.uncertain} aria-describedby="document-file-hint" aria-invalid={state.error?.kind === 'validation'} onChange={(event) => flow.select(event.target.files?.[0] ?? null)} />
        <p id="document-file-hint" className="hint">Choose exactly one file. Validation runs in the background after upload.</p>
      </div>
      {state.file && <p className="document-filename">Selected: <strong>{state.file.name}</strong> ({state.file.size.toLocaleString('en-US')} bytes)</p>}
      {state.uncertain && <div className="notice" role="status"><h3>The upload response was lost or could not be confirmed</h3>
        <p>The document may already exist. Check this upload's status first. A retry sends the same file with the same attempt key; it does not retry background processing.</p>
        <button type="button" disabled={state.pending} onClick={() => { void flow.recover(saved) }}>Check upload status</button>
        {state.recovery === 'absent' && <p>No record was found yet. This does not rule out an upload still being finalized.</p>}
        {clock < state.replayAfter && <p>A same-attempt resend is available after {new Date(state.replayAfter).toISOString()} (UTC), after checking status.</p>}
      </div>}
      <div className="actions"><button className="primary-button" type="submit" disabled={state.pending || !state.file || (state.uncertain && (!state.recovery || clock < state.replayAfter))}>{state.pending ? 'Please wait…' : state.uncertain ? 'Retry same upload' : 'Upload file'}</button>
        {state.file && <button type="button" disabled={state.pending} onClick={() => { flow.reset(); if (input.current) input.current.value = '' }}>Start a new upload attempt</button>}
      </div>
    </form>
    <p className="hint">A new selection gets a new attempt key. No write is automatically resent. Leaving this page, reloading, signing out or changing workspaces clears the selection and its in-memory attempt. After an uncertain response, inspect the original workspace's Documents list before starting a new attempt.</p>
  </section>
}
