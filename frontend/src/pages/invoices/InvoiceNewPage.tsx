import { useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ApiFailure, createInvoice } from '../../api.ts'
import type { InvoiceDraft } from '../../types.ts'
import { navigate } from '../../navigation.ts'
import { focusError, invoicePayload, newInvoiceDraft, validateInvoice } from '../../validation.ts'
import { selectInvoiceOrder, selectInvoiceSupplier } from '../../selections.ts'
import { useSave } from '../../hooks/useBusiness.ts'
import type { SaveFeedback } from '../../hooks/useBusiness.ts'
import { useSelectedOrder } from '../../hooks/useSelectedOrder.ts'
import { FormFeedback, TextField } from '../../components/FormFeedback.tsx'
import SupplierPicker from '../../components/SupplierPicker.tsx'
import OrderPicker from '../../components/OrderPicker.tsx'
import LineItemsForm from '../../components/LineItemsForm.tsx'
import RequestState from '../../components/RequestState.tsx'

export default function InvoiceNewPage({ draft, setDraft, feedback, setFeedback }: {
  draft: InvoiceDraft; setDraft: Dispatch<SetStateAction<InvoiceDraft>>
  feedback: SaveFeedback; setFeedback: Dispatch<SetStateAction<SaveFeedback>>
}) {
  const form = useRef<HTMLFormElement>(null)
  const save = useSave(setFeedback)
  const order = useSelectedOrder(draft.order, draft.supplier?.id)
  const details = feedback.error?.details ?? []
  const orderReady = !draft.order || order.data !== null
  useEffect(() => { if (feedback.error && form.current) focusError(form.current, feedback.error.details) }, [feedback.error])
  const update = (field: 'invoice_number' | 'invoice_date' | 'due_date' | 'tax_amount' | 'notes', value: string) => setDraft((current) => ({ ...current, [field]: value }))

  return <section className="business-panel"><h2>Create invoice</h2>
    <p>Choose a supplier, enter the invoice fields and priced lines, and enter its tax amount. The invoice will be saved as a draft.</p>
    <form ref={form} noValidate aria-busy={feedback.pending} onSubmit={(event) => {
      event.preventDefault()
      if (feedback.pending) return
      const input = invoicePayload(draft)
      const errors = validateInvoice(input, order.data)
      if (!orderReady) errors.push({ field: 'purchase_order_id', message: 'Wait for the selected order to load, or retry loading it before saving.' })
      if (errors.length) { setFeedback({ pending: false, error: new ApiFailure('validation', 'Some fields are invalid.', errors) }); return }
      void save((signal) => createInvoice(input, { signal }), (saved) => { setDraft(newInvoiceDraft()); navigate(`#/invoices/${saved.id}`) })
    }}>
      <FormFeedback error={feedback.error} listHref="#/invoices" />
      <fieldset className="form-controls" disabled={feedback.pending}><legend className="sr-only">Invoice fields</legend>
        <SupplierPicker selected={draft.supplier} details={details} documentName="draft invoice" onSelect={(supplier) => setDraft((current) => selectInvoiceSupplier(current, supplier))} />
        {draft.supplier ? <>
          <OrderPicker key={draft.supplier.id} selected={draft.order} supplierId={draft.supplier.id} optional details={details} onSelect={(selected) => setDraft((current) => selectInvoiceOrder(current, selected))} />
          {draft.order && <div aria-busy={order.loading}><RequestState loading={order.loading} error={order.error} retry={order.retry} /></div>}
        </> : <p className="hint">Choose a supplier before selecting an optional purchase order. You can also save the invoice without an order.</p>}
        <p className="hint">Changing supplier clears the selected order and manual line links. Changing order clears those line links. Your entered invoice fields and priced lines are kept.</p>
        <div className="field-grid">
          <TextField id="invoice-number" field="invoice_number" label="Invoice number" value={draft.invoice_number} onChange={(value) => update('invoice_number', value)} details={details} hint="Required; up to 64 characters. Numbers are case-sensitive within a supplier." />
          <TextField id="invoice-date" field="invoice_date" label="Invoice date" type="date" value={draft.invoice_date} onChange={(value) => update('invoice_date', value)} details={details} hint="Required calendar date." />
        </div>
        <div className="field-grid">
          <TextField id="invoice-due-date" field="due_date" label="Due date (optional)" type="date" value={draft.due_date} onChange={(value) => update('due_date', value)} details={details} hint="Cannot be before the invoice date." />
          <div className="form-field"><label htmlFor="invoice-currency">Currency</label><input id="invoice-currency" value="EUR" readOnly /></div>
        </div>
        <TextField id="invoice-tax" field="tax_amount" label="Tax amount (EUR)" value={draft.tax_amount} onChange={(value) => update('tax_amount', value)} details={details} decimal hint="Required invoice-level amount, not a percentage. Enter 0.00 when there is no tax. Up to 2 decimal places; maximum 9999999999999999.99." />
        <TextField id="invoice-notes" field="notes" label="Notes (optional)" value={draft.notes} onChange={(value) => update('notes', value)} details={details} hint="Up to 2000 characters." multiline />
        <LineItemsForm lines={draft.lines} details={details} allowMapping mappingOrder={order.data} onChange={(lines) => setDraft((current) => ({ ...current, lines }))} />
        <button className="primary-button" type="submit" disabled={!orderReady}>{feedback.pending ? 'Saving…' : 'Save draft invoice'}</button>
      </fieldset>
      <p className="form-cancel"><a href="#/invoices">Cancel</a></p>
    </form>
  </section>
}
