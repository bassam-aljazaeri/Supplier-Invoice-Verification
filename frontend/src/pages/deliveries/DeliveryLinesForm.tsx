import type { DeliveryLineDraft, ErrorDetail, PurchaseOrder } from '../../types.ts'
import { fieldError } from '../../validation.ts'
import { TextField } from '../../components/FormFeedback.tsx'

export default function DeliveryLinesForm({ order, lines, details, onSelect, onQuantity }: {
  order: PurchaseOrder
  lines: DeliveryLineDraft[]
  details: ErrorDetail[]
  onSelect: (lineId: string, selected: boolean) => void
  onQuantity: (key: string, quantity: string) => void
}) {
  const error = fieldError(details, 'lines')
  return <fieldset className="line-items" tabIndex={-1} data-field="lines" aria-invalid={!!error} aria-describedby={error ? 'delivery-lines-error' : 'delivery-lines-hint'}>
    <legend>Received lines</legend>
    <p className="hint" id="delivery-lines-hint">Choose 1–100 lines from this order. Enter the quantity received for each chosen line. Each order line can appear once in this receipt.</p>
    {error && <p className="field-error" id="delivery-lines-error">{error}</p>}
    {order.lines.map((orderLine) => {
      const index = lines.findIndex((line) => line.purchase_order_line_id === orderLine.id)
      const selected = index >= 0 ? lines[index] : null
      const mappingError = selected ? fieldError(details, `lines[${index}].purchase_order_line_id`) : ''
      const lineError = selected ? fieldError(details, `lines[${index}]`) : ''
      const checkboxId = `delivery-order-line-${orderLine.id}`
      return <fieldset className="line-card" key={orderLine.id} tabIndex={-1} data-field={selected ? `lines[${index}]` : undefined} aria-invalid={!!lineError} aria-describedby={lineError ? `${checkboxId}-line-error` : undefined}>
        <legend>Order line {orderLine.line_no}</legend>
        {lineError && <p className="field-error" id={`${checkboxId}-line-error`}>{lineError}</p>}
        <div className="delivery-line-choice">
          <input id={checkboxId} type="checkbox" checked={!!selected} data-field={selected ? `lines[${index}].purchase_order_line_id` : undefined} aria-invalid={!!mappingError} aria-describedby={mappingError ? `${checkboxId}-error` : undefined} onChange={(event) => onSelect(orderLine.id, event.target.checked)} />
          <label htmlFor={checkboxId}>{orderLine.description}</label>
        </div>
        {mappingError && <p className="field-error" id={`${checkboxId}-error`}>{mappingError}</p>}
        {selected && <TextField id={`delivery-quantity-${selected.key}`} field={`lines[${index}].quantity_received`} label={`Quantity received for order line ${orderLine.line_no}`} value={selected.quantity_received} details={details} decimal hint="Positive; up to 3 decimal places. Maximum 999999999.999." onChange={(quantity) => onQuantity(selected.key, quantity)} />}
      </fieldset>
    })}
    <p role="status">{lines.length} of {order.lines.length} order lines selected</p>
  </fieldset>
}
