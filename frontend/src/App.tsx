import { useCallback, useEffect, useRef, useState } from 'react'
import { getHealthStatus, getReadinessStatus, initialStatus } from './status'
import type { CheckState, StatusSnapshot } from './status'
import './App.css'

const labels: Record<CheckState, string> = {
  loading: 'Checking...',
  ok: 'Available',
  unavailable: 'Unavailable',
  failed: 'Request failed',
  timed_out: 'Request timed out',
}

function StatusCard({ title, state }: { title: string; state: CheckState }) {
  return (
    <li className="status-card">
      <h3>{title}</h3>
      <p className={`status-value status-${state}`} aria-live="polite">
        <span className="status-dot" aria-hidden="true" />
        {labels[state]}
      </p>
    </li>
  )
}

function App() {
  const [status, setStatus] = useState<StatusSnapshot>(initialStatus)
  const [refreshing, setRefreshing] = useState(false)
  const activeRequest = useRef<AbortController | null>(null)

  const refreshStatus = useCallback(async () => {
    // The ref blocks repeat clicks before React updates the disabled button.
    if (activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setRefreshing(true)
    setStatus(initialStatus)

    try {
      await Promise.all([
        getHealthStatus({ signal: controller.signal }).then((api) => {
          if (!controller.signal.aborted) {
            setStatus((current) => ({ ...current, api }))
          }
        }),
        getReadinessStatus({ signal: controller.signal }).then((dependencies) => {
          if (!controller.signal.aborted) {
            setStatus((current) => ({ ...current, ...dependencies }))
          }
        }),
      ])
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null
        if (!controller.signal.aborted) setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
    return () => {
      activeRequest.current?.abort()
      activeRequest.current = null
    }
  }, [refreshStatus])

  const states = Object.values(status)
  let statusNote = 'All checks completed. Use Refresh status to check again.'
  if (refreshing) {
    statusNote = 'Checking the local API and its dependencies.'
  } else if (states.includes('failed') || states.includes('timed_out')) {
    statusNote = 'Some checks could not finish. Check the backend and refresh status.'
  } else if (states.includes('unavailable')) {
    statusNote = 'Some services are unavailable. Restore the service and refresh status.'
  }

  return (
    <main className="page-shell">
      <header className="page-header">
        <p className="eyebrow">Local development</p>
        <h1>Supplier-Invoice-Verification</h1>
        <p className="intro">
          Check the API and the services it needs before development work.
        </p>
      </header>

      <section className="status-panel" aria-labelledby="status-heading" aria-busy={refreshing}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Service status</p>
            <h2 id="status-heading">Development environment</h2>
          </div>
          <button
            className="refresh-button"
            type="button"
            onClick={() => void refreshStatus()}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh status'}
          </button>
        </div>

        <ul className="status-list" aria-label="Service health checks">
          <StatusCard title="API health" state={status.api} />
          <StatusCard title="PostgreSQL readiness" state={status.database} />
          <StatusCard title="Redis readiness" state={status.redis} />
        </ul>

        <p className="status-note" role="status">{statusNote}</p>
      </section>

      <footer className="page-footer">
        <span>Supplier-Invoice-Verification</span>
        <span>Local services at 127.0.0.1</span>
      </footer>
    </main>
  )
}

export default App
