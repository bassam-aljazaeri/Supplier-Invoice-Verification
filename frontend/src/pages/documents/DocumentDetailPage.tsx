import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { getDocument, downloadDocument, retryDocument } from '../../documentApi.ts'
import { documentErrorMessage, documentStatus } from '../../documentTypes.ts'
import type { DocumentRecord } from '../../documentTypes.ts'
import { createDocumentPoller } from '../../documentPolling.ts'
import { subscribeHashChange } from '../../navigation.ts'
import { useCanCreate } from '../../authContext.tsx'
import { useSave } from '../../hooks/useBusiness.ts'
import type { SaveFeedback } from '../../hooks/useBusiness.ts'
import RequestState from '../../components/RequestState.tsx'
import { ApiFailure } from '../../api.ts'
import { openExternalDownload } from '../../documentDownloads.ts'

export function DocumentActions({ record, refresh }: { record: DocumentRecord; refresh: () => void }) {
  const canRetry = useCanCreate()
  const [feedback, setFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const save = useSave(setFeedback)
  const objectUrl = useRef<string | null>(null), releaseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    const release = () => {
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
      objectUrl.current = null
      if (releaseTimer.current) clearTimeout(releaseTimer.current)
    }
    const unsubscribe = subscribeHashChange(release)
    return () => { release(); unsubscribe() }
  }, [])
  return <div className="document-actions">
    {feedback.error && <div className="error-summary" role="alert"><p>{feedback.error.kind === 'conflict' ? 'The document is no longer eligible for this action. Refresh its status.' : feedback.error.message}</p>
      {feedback.error.uncertainWrite && <p>The processing retry may already be queued. Refresh status before choosing another action. The original file will not be uploaded again.</p>}
      <button type="button" onClick={refresh}>Refresh status</button>
    </div>}
    {record.state === 'accepted' && <><p>Download an attachment. A fresh short-lived authorization is requested each time. A storage link already issued can remain usable until expiry, even if workspace access changes.</p><button type="button" disabled={feedback.pending} onClick={() => { void save((signal) => downloadDocument(record, { signal }), (download) => {
      if (download.delivery === 's3_presigned') { openExternalDownload(download.url); return }
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
      if (releaseTimer.current) clearTimeout(releaseTimer.current)
      objectUrl.current = null; releaseTimer.current = null
      const url = URL.createObjectURL(download.blob)
      objectUrl.current = url
      const link = document.createElement('a')
      link.href = url; link.download = download.filename; link.rel = 'noreferrer'
      try { document.body.append(link); link.click() } catch {
        URL.revokeObjectURL(url); objectUrl.current = null
        throw new ApiFailure('server', 'The attachment could not be downloaded. Request a fresh download.')
      } finally { link.remove() }
      releaseTimer.current = setTimeout(() => { URL.revokeObjectURL(url); if (objectUrl.current === url) objectUrl.current = null }, 1000)
    }) }}> {feedback.pending ? 'Preparing download…' : 'Download accepted document'}</button></>}
    {record.state === 'failed' && canRetry && <>
      <p>Retry processing uses the existing stored file. It is different from resending an upload with a lost response. Eligible failures have one additional cycle after the cooldown; the backend checks eligibility again.</p>
      {record.can_retry && !feedback.error?.uncertainWrite ? <button type="button" disabled={feedback.pending} onClick={() => { void save((signal) => retryDocument(record.id, { signal }), refresh) }}>{feedback.pending ? 'Requesting retry…' : 'Retry processing'}</button>
        : <p>No processing retry is currently offered. Permanent upload/storage failures or an exhausted retry budget are ineligible. Refresh after the cooldown to check again.</p>}
    </>}
  </div>
}

export function DocumentMetadata({ record }: { record: DocumentRecord }) {
  return <>
    <h3 className="document-filename">{record.original_filename}</h3>
    <p role="status"><strong className="document-state">{record.state}</strong> — {documentStatus[record.state]}</p>
    {record.error_code && <p role="status">{documentErrorMessage[record.error_code]}</p>}
    <p>Accepted means file validation passed. It does not mean an invoice was matched or approved. No invoice is created or linked automatically.</p>
    <dl className="record-fields">
      <dt>Document ID</dt><dd className="identity-id">{record.id}</dd><dt>Workspace</dt><dd className="identity-id">{record.workspace_id}</dd>
      <dt>Uploader ID</dt><dd className="identity-id">{record.uploader_id}</dd><dt>Bytes</dt><dd>{record.byte_size.toLocaleString('en-US')}</dd>
      <dt>Validated type</dt><dd>{record.detected_type?.toUpperCase() ?? 'Not validated'}</dd>
      <dt>Created (UTC)</dt><dd>{record.created_at}</dd><dt>Uploaded (UTC)</dt><dd>{record.uploaded_at ?? 'Not finalized'}</dd>
      <dt>Updated (UTC)</dt><dd>{record.updated_at}</dd><dt>Finished (UTC)</dt><dd>{record.finished_at ?? 'Not finished'}</dd>
      {record.error_code && <><dt>Safe error code</dt><dd>{record.error_code}</dd></>}
    </dl>
  </>
}

export default function DocumentDetailPage({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getDocument(id, { signal, timeoutMs: 5000 }), [id])
  const [poller] = useState(() => createDocumentPoller(load))
  const state = useSyncExternalStore(poller.subscribe, poller.snapshot, poller.snapshot)
  useEffect(() => {
    poller.start(document.visibilityState !== 'hidden')
    const visibility = () => { if (document.visibilityState === 'hidden') poller.pause() }
    const unsubscribe = subscribeHashChange(poller.dispose)
    document.addEventListener('visibilitychange', visibility)
    return () => { poller.dispose(); unsubscribe(); document.removeEventListener('visibilitychange', visibility) }
  }, [poller])
  const refresh = () => { if (document.visibilityState !== 'hidden') poller.refresh() }
  return <section className="business-panel" aria-busy={state.busy}>
    <div className="panel-heading"><h2>Document details</h2><a href="#/documents">Back to documents</a></div>
    <RequestState loading={state.busy && !state.data} error={state.error} retry={refresh} />
    <button type="button" onClick={refresh} disabled={state.busy}>Refresh status</button>
    {state.reason === 'hidden' && <p role="status">Automatic checking paused while the tab was hidden. Refresh status to resume.</p>}
    {state.reason === 'limit' && <p role="status">Automatic checking paused after its limit. Use Refresh status for another read.</p>}
    {state.data && <><DocumentMetadata record={state.data} /><DocumentActions key={state.revision} record={state.data} refresh={refresh} /></>}
  </section>
}
