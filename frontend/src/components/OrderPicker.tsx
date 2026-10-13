import { useCallback, useState } from 'react'
import { getPurchaseOrders } from '../api.ts'
import type { ErrorDetail, PurchaseOrderSummary } from '../types.ts'
import { fieldError } from '../validation.ts'
import { useRead } from '../hooks/useBusiness.ts'
import Pagination from './Pagination.tsx'
import RequestState from './RequestState.tsx'

export default function OrderPicker({ selected, onSelect, details, supplierId, optional = false }: {
  selected: PurchaseOrderSummary | null; onSelect: (order: PurchaseOrderSummary | null) => void
  details: ErrorDetail[]; supplierId?: string; optional?: boolean
}) {
  const [offset, setOffset] = useState(0)
  const load = useCallback((signal: AbortSignal) => getPurchaseOrders({ limit: 20, offset, supplier_id: supplierId }, { signal }), [offset, supplierId])
  const result = useRead(`order-picker-${supplierId ?? 'all'}-${offset}`, load)
  const error = fieldError(details, 'purchase_order_id')
  return <fieldset className="supplier-picker" data-field="purchase_order_id" tabIndex={-1} aria-invalid={!!error} aria-describedby={error ? 'purchase-order-error' : undefined}>
    <legend>Purchase order{optional ? ' (optional)' : ''}</legend>
    <p className="hint">Choose by order number. Use Previous and Next to browse all available pages.</p>
    {selected && <p className="selected-supplier">Selected: <strong>{selected.po_number}</strong> ({selected.order_date})</p>}
    {error && <p className="field-error" id="purchase-order-error">{error}</p>}
    {optional && <label className="order-option" htmlFor="no-purchase-order"><input id="no-purchase-order" type="radio" name="purchase_order_id" checked={!selected} onChange={() => onSelect(null)} /> No purchase order</label>}
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      {result.data.items.length ? <ul className="supplier-options">{result.data.items.map((order) => <li key={order.id}><label htmlFor={`order-choice-${order.id}`}>
        <input id={`order-choice-${order.id}`} type="radio" name="purchase_order_id" checked={selected?.id === order.id} onChange={() => onSelect(order)} />
        <span>{order.po_number} — {order.order_date}</span>
      </label></li>)}</ul> : <p>{result.data.total ? 'No orders on this page. Use Previous to return to earlier records.' : optional ? 'No orders for this supplier. You can save an invoice without an order.' : 'Create a purchase order first before recording a delivery.'}</p>}
      <Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={setOffset} />
    </>}
    <a href="#/purchase-orders/new">Create a purchase order</a>
  </fieldset>
}
