import { useState } from 'react'
import { createWorkspace } from '../accountApi.ts'
import { useSession } from '../authContext.tsx'
import { useSave } from '../hooks/useBusiness.ts'
import type { SaveFeedback } from '../hooks/useBusiness.ts'
import { FormFeedback, TextField } from '../components/FormFeedback.tsx'
import { navigate } from '../navigation.ts'

export default function WorkspaceNewPage() {
  const { session } = useSession()
  const [slug, setSlug] = useState(''), [name, setName] = useState('')
  const [feedback, setFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const save = useSave(setFeedback)
  return <section className="business-panel"><h2>Create a workspace</h2>
    <p>The workspace and your first administrator membership will be saved together. This grants no access to existing workspaces.</p>
    <form noValidate aria-busy={feedback.pending} onSubmit={(event) => {
      event.preventDefault()
      void save((signal) => createWorkspace({ slug, name }, { signal }), () => { navigate('#/account'); void session.refreshAccess() })
    }}>
      <FormFeedback error={feedback.error} listHref="#/account" />
      <fieldset disabled={feedback.pending} className="form-controls"><legend className="sr-only">Workspace fields</legend>
        <TextField id="workspace-name" field="name" label="Workspace name" value={name} onChange={setName} details={feedback.error?.details ?? []} hint="Required; up to 200 characters." />
        <TextField id="workspace-slug" field="slug" label="Workspace slug" value={slug} onChange={setSlug} details={feedback.error?.details ?? []} hint="1–64 lowercase letters/digits separated by single hyphens. local-demo is reserved." />
        <button type="submit" className="primary-button">{feedback.pending ? 'Creating…' : 'Create workspace'}</button>
      </fieldset>
    </form><p><a href="#/account">Cancel</a></p>
  </section>
}
