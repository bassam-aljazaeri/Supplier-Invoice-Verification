import { useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ApiFailure, createPurchaseOrder } from '../../api.ts'
import type { OrderDraft } from '../../types.ts'
import { navigate } from '../../navigation.ts'
import { focusError, newOrderDraft, orderPayload, validateOrder } from '../../validation.ts'
import { useSave } from '../../hooks/useBusiness.ts'
import type { SaveFeedback } from '../../hooks/useBusiness.ts'
import { FormFeedback, TextField } from '../../components/FormFeedback.tsx'
import SupplierPicker from '../../components/SupplierPicker.tsx'
import LineItemsForm from '../../components/LineItemsForm.tsx'

export default function PurchaseOrderNewPage({ draft, setDraft, feedback, setFeedback }: { draft: OrderDraft; setDraft: Dispatch<SetStateAction<OrderDraft>>; feedback: SaveFeedback; setFeedback: Dispatch<SetStateAction<SaveFeedback>> }) {
  const form = useRef<HTMLFormElement>(null)
  const save = useSave(setFeedback)
  const details = feedback.error?.details ?? []
  useEffect(() => { if (feedback.error && form.current) focusError(form.current, feedback.error.details) }, [feedback.error])
  const update = (field: 'po_number' | 'order_date' | 'notes', value: string) => setDraft((current) => ({ ...current, [field]: value }))
  return <section className="business-panel"><h2>Create purchase order</h2><p>Choose a supplier, enter the order date, and add the items you are ordering.</p>
    <form ref={form} noValidate aria-busy={feedback.pending} onSubmit={(event) => {
      event.preventDefault()
      if (feedback.pending) return
      const input = orderPayload(draft)
      const errors = validateOrder(input)
      if (errors.length) { setFeedback({ pending: false, error: new ApiFailure('validation', 'Some fields are invalid.', errors) }); return }
      void save((signal) => createPurchaseOrder(input, { signal }), (saved) => { setDraft(newOrderDraft()); navigate(`#/purchase-orders/${saved.id}`) })
    }}>
      <FormFeedback error={feedback.error} listHref="#/purchase-orders" />
      <fieldset className="form-controls" disabled={feedback.pending}><legend className="sr-only">Purchase-order fields</legend>
        <SupplierPicker selected={draft.supplier} details={details} onSelect={(supplier) => setDraft((current) => ({ ...current, supplier }))} />
        <div className="field-grid">
          <TextField id="order-number" field="po_number" label="Order number" value={draft.po_number} onChange={(value) => update('po_number', value)} details={details} hint="Required; up to 64 characters. Numbers are case-sensitive." />
          <TextField id="order-date" field="order_date" label="Order date" type="date" value={draft.order_date} onChange={(value) => update('order_date', value)} details={details} hint="Required calendar date." />
        </div>
        <div className="form-field"><label htmlFor="order-currency">Currency</label><input id="order-currency" value="EUR" readOnly /></div>
        <TextField id="order-notes" field="notes" label="Notes (optional)" value={draft.notes} onChange={(value) => update('notes', value)} details={details} hint="Up to 2000 characters." multiline />
        <LineItemsForm lines={draft.lines} details={details} onChange={(lines) => setDraft((current) => ({ ...current, lines }))} />
        <button className="primary-button" type="submit">{feedback.pending ? 'Saving…' : 'Save purchase order'}</button>
      </fieldset>
      <p className="form-cancel"><a href="#/purchase-orders">Cancel</a></p>
    </form>
  </section>
}
