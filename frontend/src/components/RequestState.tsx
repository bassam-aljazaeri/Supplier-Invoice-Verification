import type { ApiFailure } from '../api.ts'

const titles = { validation: 'Invalid request', conflict: 'Identifier already exists', missing: 'Record not found', unavailable: 'Service unavailable', server: 'Server error', network: 'Connection failed', timeout: 'Request timed out', cancelled: 'Request interrupted', 'invalid-response': 'Response could not be read' }

export default function RequestState({ loading, error, retry }: { loading: boolean; error: ApiFailure | null; retry: () => void }) {
  if (loading) return <p role="status">Loading records…</p>
  if (!error) return null
  return <div className="request-error" role="alert"><h3>{titles[error.kind]}</h3><p>{error.message}</p>
    {error.kind === 'missing' && <p>The record may be unavailable. Check the list for another record.</p>}
    <div className="actions"><button type="button" onClick={retry}>Retry</button><a href="#/status">Check service status</a></div>
  </div>
}
