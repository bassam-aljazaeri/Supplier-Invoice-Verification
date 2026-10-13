import { useCallback } from 'react'
import { getInvoices } from '../api.ts'
import type { InvoiceParams } from '../types.ts'
import { useRead } from '../hooks/useBusiness.ts'
import Pagination from './Pagination.tsx'
import RequestState from './RequestState.tsx'

export default function InvoiceList({ page, onPage }: { page: InvoiceParams; onPage: (offset: number) => void }) {
  const { limit, offset, supplier_id, purchase_order_id } = page
  const load = useCallback((signal: AbortSignal) => getInvoices({ limit, offset, supplier_id, purchase_order_id }, { signal }), [limit, offset, supplier_id, purchase_order_id])
  const result = useRead(`invoices-${supplier_id ?? 'all'}-${purchase_order_id ?? 'all'}-${limit}-${offset}`, load)
  return <div aria-busy={result.loading}><RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      {result.data.items.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Invoice table"><table><caption className="sr-only">Saved draft invoices</caption>
        <thead><tr><th scope="col">Invoice number</th><th scope="col">Invoice date</th><th scope="col">Status</th><th scope="col">Total (EUR)</th></tr></thead>
        <tbody>{result.data.items.map((invoice) => <tr key={invoice.id}><td><a href={`#/invoices/${invoice.id}`}>{invoice.invoice_number}</a></td><td>{invoice.invoice_date}</td><td>{invoice.status}</td><td className="decimal">{invoice.total}</td></tr>)}</tbody>
      </table></div> : <p>{result.data.total ? 'No invoices on this page. Use Previous to return to earlier records.' : 'No invoices yet for this list.'}</p>}
      <Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={onPage} />
    </>}
  </div>
}
