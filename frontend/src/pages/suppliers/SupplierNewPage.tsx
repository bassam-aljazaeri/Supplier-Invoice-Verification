import { useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ApiFailure, createSupplier } from '../../api.ts'
import type { SupplierDraft } from '../../types.ts'
import { navigate } from '../../navigation.ts'
import { focusError, newSupplierDraft, supplierPayload, validateSupplier } from '../../validation.ts'
import { useSave } from '../../hooks/useBusiness.ts'
import type { SaveFeedback } from '../../hooks/useBusiness.ts'
import { FormFeedback, TextField } from '../../components/FormFeedback.tsx'

export default function SupplierNewPage({ draft, setDraft, feedback, setFeedback }: { draft: SupplierDraft; setDraft: Dispatch<SetStateAction<SupplierDraft>>; feedback: SaveFeedback; setFeedback: Dispatch<SetStateAction<SaveFeedback>> }) {
  const form = useRef<HTMLFormElement>(null)
  const save = useSave(setFeedback)
  const details = feedback.error?.details ?? []
  useEffect(() => { if (feedback.error && form.current) focusError(form.current, feedback.error.details) }, [feedback.error])
  const update = (field: keyof SupplierDraft, value: string) => setDraft((current) => ({ ...current, [field]: value }))
  return <section className="business-panel"><h2>Create supplier</h2><p>Enter a supplier code and name. Notes are optional.</p>
    <form ref={form} noValidate aria-busy={feedback.pending} onSubmit={(event) => {
      event.preventDefault()
      if (feedback.pending) return
      const input = supplierPayload(draft)
      const errors = validateSupplier(input)
      if (errors.length) { setFeedback({ pending: false, error: new ApiFailure('validation', 'Some fields are invalid.', errors) }); return }
      void save((signal) => createSupplier(input, { signal }), (saved) => { setDraft(newSupplierDraft()); navigate(`#/suppliers/${saved.id}`) })
    }}>
      <FormFeedback error={feedback.error} listHref="#/suppliers" />
      <fieldset disabled={feedback.pending} className="form-controls"><legend className="sr-only">Supplier fields</legend>
        <TextField id="supplier-code" field="supplier_code" label="Supplier code" value={draft.supplier_code} onChange={(value) => update('supplier_code', value)} details={details} hint="Required; up to 64 characters. Codes are case-sensitive." />
        <TextField id="supplier-name" field="name" label="Supplier name" value={draft.name} onChange={(value) => update('name', value)} details={details} hint="Required; up to 200 characters." />
        <TextField id="supplier-notes" field="notes" label="Notes (optional)" value={draft.notes} onChange={(value) => update('notes', value)} details={details} hint="Up to 2000 characters." multiline />
        <button className="primary-button" type="submit">{feedback.pending ? 'Saving…' : 'Save supplier'}</button>
      </fieldset>
      <p className="form-cancel"><a href="#/suppliers">Cancel</a></p>
    </form>
  </section>
}
