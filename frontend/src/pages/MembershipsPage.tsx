import { useCallback, useState } from 'react'
import { addMembership, changeMembership, getMemberships, removeMembership } from '../accountApi.ts'
import { useSession } from '../authContext.tsx'
import type { Membership, Role } from '../authTypes.ts'
import { useRead, useSave } from '../hooks/useBusiness.ts'
import type { SaveFeedback } from '../hooks/useBusiness.ts'
import { FormFeedback, TextField } from '../components/FormFeedback.tsx'
import RequestState from '../components/RequestState.tsx'
import Pagination from '../components/Pagination.tsx'

const roles: Role[] = ['administrator', 'accountant', 'approver']
function RoleSelect({ value, onChange, label, disabled }: { value: Role; onChange: (role: Role) => void; label: string; disabled?: boolean }) {
  return <label>{label}<select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value as Role)}>{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
}
function MemberRow({ member, pending, change, remove }: { member: Membership; pending: boolean; change: (role: Role) => void; remove: () => void }) {
  const [role, setRole] = useState(member.role)
  return <tr><td><code className="identity-id">{member.application_user_id}</code></td><td>{member.role}</td><td>
    <RoleSelect label={`New role for ${member.application_user_id}`} value={role} onChange={setRole} disabled={pending} />
    <div className="actions"><button type="button" disabled={pending || role === member.role} onClick={() => change(role)}>Save role</button><button type="button" disabled={pending} onClick={remove}>Remove membership</button></div>
  </td></tr>
}
export default function MembershipsPage() {
  const { session, selected, me } = useSession()
  const workspaceId = selected!.workspace_id
  const [offset, setOffset] = useState(0), [revision, setRevision] = useState(0)
  const [userId, setUserId] = useState(''), [role, setRole] = useState<Role>('approver')
  const [message, setMessage] = useState('')
  const [feedback, setFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const save = useSave(setFeedback)
  const load = useCallback((signal: AbortSignal) => getMemberships(workspaceId, offset, { signal }), [workspaceId, offset])
  const result = useRead(`members-${workspaceId}-${offset}-${revision}`, load)
  const completed = (target?: string) => {
    setMessage('Membership change saved.')
    setRevision((v) => v + 1)
    if (target === me?.user.id) void session.refreshAccess('Your membership changed. Access has been refreshed.')
  }
  return <section className="business-panel"><h2>Memberships — {selected!.workspace.name}</h2>
    <p>Add an existing active application user by their application-user ID. Ask a newly signed-in person to copy it from Account. There is no email lookup or automatic invitation.</p>
    <p>The last active administrator cannot be removed or demoted. Concurrent conflicts are checked by the server.</p>
    <button type="button" disabled={feedback.pending} onClick={() => setRevision((value) => value + 1)}>Refresh memberships</button>
    <FormFeedback error={feedback.error} listHref="#/memberships" />
    {feedback.error?.kind === 'conflict' && <p role="alert">Membership conflict: the assignment may already exist, or this change would remove the last active administrator. Refresh the list before choosing another action.</p>}
    <p role="status">{message}</p>
    <form noValidate aria-busy={feedback.pending} onSubmit={(event) => {
      event.preventDefault(); setMessage('')
      void save((signal) => addMembership(workspaceId, userId.trim(), role, { signal }), () => { setUserId(''); completed() })
    }}><fieldset className="form-controls" disabled={feedback.pending}><legend>Add membership</legend>
      <TextField id="member-user" field="application_user_id" label="Application-user ID" value={userId} onChange={setUserId} details={feedback.error?.details ?? []} />
      <RoleSelect label="Role" value={role} onChange={setRole} />
      <button type="submit" className="primary-button">Add membership</button>
    </fieldset></form>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <><div className="table-scroll"><table><caption>Current workspace memberships</caption><thead><tr><th>Application-user ID</th><th>Current role</th><th>Actions</th></tr></thead><tbody>
      {result.data.items.map((member) => <MemberRow key={`${member.id}-${member.updated_at}`} member={member} pending={feedback.pending} change={(next) => { setMessage(''); void save((signal) => changeMembership(workspaceId, member.application_user_id, next, { signal }), () => completed(member.application_user_id)) }} remove={() => { setMessage(''); void save((signal) => removeMembership(workspaceId, member.application_user_id, { signal }), () => completed(member.application_user_id)) }} />)}
    </tbody></table></div><Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={setOffset} /></>}
    <p><a href="#/account">Back to account</a></p>
  </section>
}
