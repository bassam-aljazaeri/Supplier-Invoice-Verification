import { useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ApiFailure, createDeliveryReceipt } from '../../api.ts'
import type { DeliveryDraft } from '../../types.ts'
import { navigate } from '../../navigation.ts'
import { deliveryPayload, focusError, newDeliveryDraft, validateDelivery } from '../../validation.ts'
import { selectDeliveryLine, selectDeliveryOrder } from '../../selections.ts'
import { useSave } from '../../hooks/useBusiness.ts'
import { useSelectedOrder } from '../../hooks/useSelectedOrder.ts'
import type { SaveFeedback } from '../../hooks/useBusiness.ts'
import { FormFeedback, TextField } from '../../components/FormFeedback.tsx'
import OrderPicker from '../../components/OrderPicker.tsx'
import RequestState from '../../components/RequestState.tsx'
import DeliveryLinesForm from './DeliveryLinesForm.tsx'

export default function DeliveryNewPage({ draft, setDraft, feedback, setFeedback }: {
  draft: DeliveryDraft
  setDraft: Dispatch<SetStateAction<DeliveryDraft>>
  feedback: SaveFeedback
  setFeedback: Dispatch<SetStateAction<SaveFeedback>>
}) {
  const form = useRef<HTMLFormElement>(null)
  const save = useSave(setFeedback)
  const selectedOrder = useSelectedOrder(draft.order)
  const order = selectedOrder.data?.id === draft.order?.id ? selectedOrder.data : null
  const details = feedback.error?.details ?? []
  useEffect(() => { if (feedback.error && form.current) focusError(form.current, feedback.error.details) }, [feedback.error])
  const update = (field: 'receipt_number' | 'received_date' | 'notes', value: string) => setDraft((current) => ({ ...current, [field]: value }))

  return <section className="business-panel">
    <h2>Create delivery record</h2>
    <p>Choose a purchase order and record what was received against its lines. Multiple receipts can belong to the same order.</p>
    <form ref={form} noValidate aria-busy={feedback.pending} onSubmit={(event) => {
      event.preventDefault()
      if (feedback.pending) return
      const input = deliveryPayload(draft)
      const errors = validateDelivery(input, order ?? undefined)
      if (draft.order && !order) errors.unshift({ field: 'purchase_order_id', message: 'Load the selected purchase order before saving. Retry its request if needed.' })
      if (errors.length) { setFeedback({ pending: false, error: new ApiFailure('validation', 'Some fields are invalid.', errors) }); return }
      void save((signal) => createDeliveryReceipt(input, { signal }), (saved) => { setDraft(newDeliveryDraft()); navigate(`#/deliveries/${saved.id}`) })
    }}>
      <FormFeedback error={feedback.error} listHref="#/deliveries" />
      <fieldset className="form-controls" disabled={feedback.pending}><legend className="sr-only">Delivery-record fields</legend>
        <OrderPicker selected={draft.order} details={details} onSelect={(chosen) => setDraft((current) => selectDeliveryOrder(current, chosen))} />
        <div className="field-grid">
          <TextField id="receipt-number" field="receipt_number" label="Receipt number" value={draft.receipt_number} details={details} hint="Required; up to 64 characters. Numbers are case-sensitive." onChange={(value) => update('receipt_number', value)} />
          <TextField id="received-date" field="received_date" label="Received date" type="date" value={draft.received_date} details={details} hint="Required calendar date." onChange={(value) => update('received_date', value)} />
        </div>
        <TextField id="receipt-notes" field="notes" label="Notes (optional)" value={draft.notes} details={details} hint="Up to 2000 characters." multiline onChange={(value) => update('notes', value)} />
        {draft.order ? <>
          <RequestState loading={selectedOrder.loading} error={selectedOrder.error} retry={selectedOrder.retry} />
          {order && <DeliveryLinesForm order={order} lines={draft.lines} details={details}
            onSelect={(lineId, selected) => setDraft((current) => selectDeliveryLine(current, lineId, selected))}
            onQuantity={(key, quantity) => setDraft((current) => ({ ...current, lines: current.lines.map((line) => line.key === key ? { ...line, quantity_received: quantity } : line) }))} />}
        </> : <p>Choose an order to see its lines and enter received quantities.</p>}
        <button className="primary-button" type="submit">{feedback.pending ? 'Saving…' : 'Save delivery record'}</button>
      </fieldset>
      <p className="form-cancel"><a href="#/deliveries">Cancel</a></p>
    </form>
  </section>
}
