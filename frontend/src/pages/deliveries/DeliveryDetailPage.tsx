import { useCallback } from 'react'
import { getDeliveryReceipt, getPurchaseOrder } from '../../api.ts'
import type { DeliveryReceipt } from '../../types.ts'
import { useRead } from '../../hooks/useBusiness.ts'
import RequestState from '../../components/RequestState.tsx'
import SupplierLink from '../../components/SupplierLink.tsx'

function ReceivedLines({ receipt }: { receipt: DeliveryReceipt }) {
  const load = useCallback((signal: AbortSignal) => getPurchaseOrder(receipt.purchase_order_id, { signal }), [receipt.purchase_order_id])
  const order = useRead(`delivery-order-${receipt.purchase_order_id}`, load)
  return <>
    <div className="related-records"><h3>Related purchase order</h3>
      <RequestState loading={order.loading} error={order.error} retry={order.retry} />
      {order.data && <dl className="record-fields"><dt>Order number</dt><dd><a href={`#/purchase-orders/${order.data.id}`}>{order.data.po_number}</a></dd><dt>Supplier</dt><dd><SupplierLink id={order.data.supplier_id} /></dd></dl>}
      {order.error && <p>The saved received quantities remain available below. Order descriptions and supplier information could not be loaded.</p>}
    </div>
    <h3>Received lines</h3>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Saved received lines"><table><caption className="sr-only">Saved receipt lines, in order</caption>
      <thead><tr><th scope="col">Receipt line</th><th scope="col">Order line</th><th scope="col">Quantity received</th></tr></thead>
      <tbody>{receipt.lines.map((line) => {
        const orderLine = order.data?.lines.find((item) => item.id === line.purchase_order_line_id)
        return <tr key={line.id}><td>{line.line_no}</td><td><a href={`#/purchase-orders/${receipt.purchase_order_id}`}>{orderLine ? `${orderLine.line_no}. ${orderLine.description}` : 'View referenced order line'}</a></td><td className="decimal">{line.quantity_received}</td></tr>
      })}</tbody>
    </table></div>
  </>
}

export default function DeliveryDetailPage({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getDeliveryReceipt(id, { signal }), [id])
  const result = useRead(`delivery-${id}`, load)
  return <section className="business-panel" aria-busy={result.loading}>
    <div className="panel-heading"><h2>Delivery-record details</h2><a href="#/deliveries">Back to delivery records</a></div>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      <dl className="record-fields"><dt>Receipt number</dt><dd>{result.data.receipt_number}</dd><dt>Received date</dt><dd>{result.data.received_date}</dd><dt>Purchase order</dt><dd><a href={`#/purchase-orders/${result.data.purchase_order_id}`}>View purchase order</a></dd><dt>Notes</dt><dd className="preserve-lines">{result.data.notes ?? 'No notes.'}</dd><dt>Created (UTC)</dt><dd>{result.data.created_at}</dd></dl>
      <ReceivedLines receipt={result.data} />
    </>}
  </section>
}
