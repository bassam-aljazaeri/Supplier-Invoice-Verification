import { useCallback } from 'react'
import { getPurchaseOrder, getSupplier } from '../../api.ts'
import { useRead } from '../../hooks/useBusiness.ts'
import RequestState from '../../components/RequestState.tsx'

function OrderSupplier({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getSupplier(id, { signal }), [id])
  const result = useRead(`order-supplier-${id}`, load)
  return <div><RequestState loading={result.loading} error={result.error} retry={result.retry} />
    <a href={`#/suppliers/${id}`}>{result.data ? `${result.data.supplier_code} — ${result.data.name}` : 'View supplier'}</a>
  </div>
}

export default function PurchaseOrderDetailPage({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getPurchaseOrder(id, { signal }), [id])
  const result = useRead(`order-${id}`, load)
  return <section className="business-panel" aria-busy={result.loading}>
    <div className="panel-heading"><h2>Purchase-order details</h2><a href="#/purchase-orders">Back to purchase orders</a></div>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      <dl className="record-fields"><dt>Order number</dt><dd>{result.data.po_number}</dd><dt>Supplier</dt><dd><OrderSupplier id={result.data.supplier_id} /></dd><dt>Order date</dt><dd>{result.data.order_date}</dd><dt>Currency</dt><dd>{result.data.currency}</dd><dt>Notes</dt><dd className="preserve-lines">{result.data.notes ?? 'No notes.'}</dd><dt>Created (UTC)</dt><dd>{result.data.created_at}</dd></dl>
      <h3>Order lines</h3><div className="table-scroll" tabIndex={0} role="region" aria-label="Saved order lines"><table><caption className="sr-only">Saved lines, in order</caption><thead><tr><th scope="col">Line</th><th scope="col">Description</th><th scope="col">Quantity</th><th scope="col">Unit price (EUR)</th><th scope="col">Line total (EUR)</th></tr></thead><tbody>
        {result.data.lines.map((line) => <tr key={line.id}><td>{line.line_no}</td><td>{line.description}</td><td className="decimal">{line.quantity}</td><td className="decimal">{line.unit_price}</td><td className="decimal">{line.line_total}</td></tr>)}
      </tbody></table></div>
      <p className="saved-total">Subtotal (EUR): <strong className="decimal">{result.data.subtotal}</strong></p>
    </>}
  </section>
}
