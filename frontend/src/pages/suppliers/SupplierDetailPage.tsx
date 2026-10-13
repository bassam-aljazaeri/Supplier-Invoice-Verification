import { useCallback, useState } from 'react'
import { getSupplier } from '../../api.ts'
import type { PageParams } from '../../types.ts'
import { listHash, navigate } from '../../navigation.ts'
import { useRead } from '../../hooks/useBusiness.ts'
import RequestState from '../../components/RequestState.tsx'
import PurchaseOrderList from '../../components/PurchaseOrderList.tsx'
import InvoiceList from '../../components/InvoiceList.tsx'

function SupplierInvoices({ id }: { id: string }) {
  const [offset, setOffset] = useState(0)
  return <section className="related-records" aria-labelledby="supplier-invoices"><div className="panel-heading"><h3 id="supplier-invoices">Invoices</h3><a href={listHash('invoices', { limit: 20, offset: 0, supplier_id: id })}>View supplier invoices</a></div>
    <InvoiceList page={{ limit: 20, offset, supplier_id: id }} onPage={setOffset} />
  </section>
}

export default function SupplierDetailPage({ id, page }: { id: string; page: PageParams }) {
  const load = useCallback((signal: AbortSignal) => getSupplier(id, { signal }), [id])
  const result = useRead(`supplier-${id}`, load)
  return <section className="business-panel" aria-busy={result.loading}>
    <div className="panel-heading"><h2>Supplier details</h2><a href="#/suppliers">Back to suppliers</a></div>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      <dl className="record-fields"><dt>Code</dt><dd>{result.data.supplier_code}</dd><dt>Name</dt><dd>{result.data.name}</dd><dt>Notes</dt><dd className="preserve-lines">{result.data.notes ?? 'No notes.'}</dd><dt>Created (UTC)</dt><dd>{result.data.created_at}</dd></dl>
      <section className="related-records" aria-labelledby="supplier-orders"><div className="panel-heading"><h3 id="supplier-orders">Purchase orders</h3><a href="#/purchase-orders/new">Create purchase order</a></div>
        <PurchaseOrderList page={{ ...page, supplier_id: id }} onPage={(offset) => navigate(listHash(`suppliers/${id}`, { ...page, offset }))} />
      </section>
      <SupplierInvoices id={id} />
    </>}
  </section>
}
