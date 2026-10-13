import { useCallback } from 'react'
import { getInvoice, getPurchaseOrder } from '../../api.ts'
import type { Invoice } from '../../types.ts'
import { useRead } from '../../hooks/useBusiness.ts'
import RequestState from '../../components/RequestState.tsx'
import SupplierLink from '../../components/SupplierLink.tsx'

function InvoiceRecord({ invoice }: { invoice: Invoice }) {
  const orderId = invoice.purchase_order_id
  const loadOrder = useCallback((signal: AbortSignal) => orderId ? getPurchaseOrder(orderId, { signal }) : Promise.resolve(null), [orderId])
  const order = useRead(`invoice-order-${invoice.id}-${orderId ?? 'none'}`, loadOrder)
  return <>
    <dl className="record-fields">
      <dt>Invoice number</dt><dd>{invoice.invoice_number}</dd>
      <dt>Supplier</dt><dd><SupplierLink id={invoice.supplier_id} /></dd>
      <dt>Purchase order</dt><dd>{orderId ? <>
        <a href={`#/purchase-orders/${orderId}`}>{order.data?.po_number ?? 'View purchase order'}</a>
        <RequestState loading={order.loading} error={order.error} retry={order.retry} />
      </> : 'No order selected.'}</dd>
      <dt>Invoice date</dt><dd>{invoice.invoice_date}</dd>
      <dt>Due date</dt><dd>{invoice.due_date ?? 'No due date.'}</dd>
      <dt>Currency</dt><dd>{invoice.currency}</dd>
      <dt>Status</dt><dd>{invoice.status}</dd>
      <dt>Notes</dt><dd className="preserve-lines">{invoice.notes ?? 'No notes.'}</dd>
      <dt>Created (UTC)</dt><dd>{invoice.created_at}</dd>
    </dl>
    <h3>Invoice lines</h3>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Saved invoice lines"><table>
      <caption className="sr-only">Saved invoice lines, in order</caption>
      <thead><tr><th scope="col">Line</th><th scope="col">Description</th><th scope="col">Quantity</th><th scope="col">Unit price (EUR)</th><th scope="col">Line total (EUR)</th><th scope="col">Manual order-line link</th></tr></thead>
      <tbody>{invoice.lines.map((line) => {
        const mapped = order.data?.lines.find((item) => item.id === line.purchase_order_line_id)
        return <tr key={line.id}>
          <td>{line.line_no}</td><td>{line.description}</td><td className="decimal">{line.quantity}</td><td className="decimal">{line.unit_price}</td><td className="decimal">{line.line_total}</td>
          <td>{line.purchase_order_line_id && orderId ? <a href={`#/purchase-orders/${orderId}`}>{mapped ? `Line ${mapped.line_no}: ${mapped.description}` : 'View manually linked order line'}</a> : 'Unmapped'}</td>
        </tr>
      })}</tbody>
    </table></div>
    <dl className="record-fields saved-total">
      <dt>Subtotal (EUR)</dt><dd className="decimal">{invoice.subtotal}</dd>
      <dt>Tax amount (EUR)</dt><dd className="decimal">{invoice.tax_amount}</dd>
      <dt>Total (EUR)</dt><dd><strong className="decimal">{invoice.total}</strong></dd>
    </dl>
    <p className="hint">Amounts are calculated when the invoice is saved. Order-line links record your manual selections.</p>
  </>
}

export default function InvoiceDetailPage({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getInvoice(id, { signal }), [id])
  const result = useRead(`invoice-${id}`, load)
  return <section className="business-panel" aria-busy={result.loading}>
    <div className="panel-heading"><h2>Invoice details</h2><a href="#/invoices">Back to invoices</a></div>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <InvoiceRecord invoice={result.data} />}
  </section>
}
