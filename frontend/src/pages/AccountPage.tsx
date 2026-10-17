import { useState } from 'react'
import { useSession } from '../authContext.tsx'
import { canManage } from '../authTypes.ts'

export default function AccountPage() {
  const { session, me, selected } = useSession()
  const [copyMessage, setCopyMessage] = useState('')
  if (!me) return null
  return <section className="business-panel"><h2>Your account and workspaces</h2>
    <p>Your application-user ID: <code className="identity-id">{me.user.id}</code></p>
    <button type="button" onClick={() => { void (navigator.clipboard?.writeText(me.user.id) ?? Promise.reject()).then(() => setCopyMessage('Application-user ID copied.')).catch(() => setCopyMessage('Select and copy the displayed ID manually.')) }}>Copy application-user ID</button>
    <p role="status">{copyMessage}</p>
    {!me.memberships.length ? <p>You have no workspace memberships yet. Give your application-user ID to a trusted workspace administrator, then refresh access, or create your own workspace. Signing in does not grant local-demo access.</p>
      : <p>Choose an accessible workspace above to open its records. Your role comes from its current membership.</p>}
    <div className="actions"><a className="button-link" href="#/workspaces/new">Create a workspace</a><button type="button" onClick={() => { void session.refreshAccess() }}>Refresh access</button>
      {canManage(selected?.role) && <a href="#/memberships">Manage memberships</a>}
    </div>
    {selected && <p><a href="#/suppliers">Open workspace suppliers</a></p>}
    <p>All roles can read records. Administrators and accountants can create them. Only administrators manage memberships. Approval actions are not available yet.</p>
  </section>
}
