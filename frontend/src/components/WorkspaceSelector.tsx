import { useSession } from '../authContext.tsx'

export default function WorkspaceSelector() {
  const { session, status, me, selected } = useSession()
  if (status !== 'ready' || !me) return null
  return <section className="workspace-bar" aria-label="Current workspace">
    <label htmlFor="active-workspace">Workspace
      <select id="active-workspace" value={selected?.workspace_id ?? ''} onChange={(event) => session.selectWorkspace(event.target.value)}>
        <option value="">{me.memberships.length ? 'Choose a workspace' : 'No workspace memberships'}</option>
        {me.memberships.map((m) => <option key={m.id} value={m.workspace_id}>{m.workspace.name} — {m.role}</option>)}
      </select>
    </label>
    {selected && <p>Current role: <strong>{selected.role}</strong></p>}
    <p className="hint">Switching workspaces clears open records and unsaved forms.</p>
  </section>
}
