import { useCallback } from 'react'
import { getDeliveryReceipts } from '../api.ts'
import type { DeliveryParams } from '../types.ts'
import { useRead } from '../hooks/useBusiness.ts'
import Pagination from './Pagination.tsx'
import RequestState from './RequestState.tsx'

export default function DeliveryList({ page, onPage }: { page: DeliveryParams; onPage: (offset: number) => void }) {
  const { limit, offset, purchase_order_id } = page
  const load = useCallback((signal: AbortSignal) => getDeliveryReceipts({ limit, offset, purchase_order_id }, { signal }), [limit, offset, purchase_order_id])
  const result = useRead(`deliveries-${purchase_order_id ?? 'all'}-${limit}-${offset}`, load)
  return <div aria-busy={result.loading}><RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      {result.data.items.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Delivery-record table"><table><caption className="sr-only">Saved delivery records</caption>
        <thead><tr><th scope="col">Receipt number</th><th scope="col">Received date</th><th scope="col">Purchase order</th></tr></thead>
        <tbody>{result.data.items.map((receipt) => <tr key={receipt.id}><td><a href={`#/deliveries/${receipt.id}`}>{receipt.receipt_number}</a></td><td>{receipt.received_date}</td><td><a href={`#/purchase-orders/${receipt.purchase_order_id}`}>View order</a></td></tr>)}</tbody>
      </table></div> : <p>{result.data.total ? 'No delivery records on this page. Use Previous to return to earlier records.' : 'No delivery records yet for this list.'}</p>}
      <Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={onPage} />
    </>}
  </div>
}
