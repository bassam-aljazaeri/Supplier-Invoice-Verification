import { useCallback } from 'react'
import { getPurchaseOrders } from '../api.ts'
import type { OrderParams } from '../types.ts'
import { useRead } from '../hooks/useBusiness.ts'
import Pagination from './Pagination.tsx'
import RequestState from './RequestState.tsx'

export default function PurchaseOrderList({ page, onPage }: { page: OrderParams; onPage: (offset: number) => void }) {
  const { limit, offset, supplier_id } = page
  const load = useCallback((signal: AbortSignal) => getPurchaseOrders({ limit, offset, supplier_id }, { signal }), [limit, offset, supplier_id])
  const result = useRead(`orders-${supplier_id ?? 'all'}-${limit}-${offset}`, load)
  return <div aria-busy={result.loading}>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      {result.data.items.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Purchase-order table"><table><caption className="sr-only">Saved purchase orders</caption><thead><tr><th scope="col">Number</th><th scope="col">Order date</th><th scope="col">Subtotal (EUR)</th></tr></thead><tbody>
        {result.data.items.map((order) => <tr key={order.id}><td><a href={`#/purchase-orders/${order.id}`}>{order.po_number}</a></td><td>{order.order_date}</td><td className="decimal">{order.subtotal}</td></tr>)}
      </tbody></table></div> : <p>{result.data.total === 0 ? 'No purchase orders yet for this list.' : 'No orders on this page. Use Previous to return to earlier records.'}</p>}
      <Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={onPage} />
    </>}
  </div>
}
