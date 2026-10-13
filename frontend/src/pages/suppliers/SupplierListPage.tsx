import { useCallback } from 'react'
import { getSuppliers } from '../../api.ts'
import type { PageParams } from '../../types.ts'
import { listHash, navigate } from '../../navigation.ts'
import { useRead } from '../../hooks/useBusiness.ts'
import Pagination from '../../components/Pagination.tsx'
import RequestState from '../../components/RequestState.tsx'

export default function SupplierListPage({ page }: { page: PageParams }) {
  const { limit, offset } = page
  const load = useCallback((signal: AbortSignal) => getSuppliers({ limit, offset }, { signal }), [limit, offset])
  const result = useRead(`suppliers-${limit}-${offset}`, load)
  return <section className="business-panel" aria-busy={result.loading}>
    <div className="panel-heading"><h2>Suppliers</h2><a className="button-link" href="#/suppliers/new">Create supplier</a></div>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      {result.data.items.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Supplier table"><table><caption className="sr-only">Saved suppliers</caption><thead><tr><th scope="col">Code</th><th scope="col">Name</th></tr></thead><tbody>{result.data.items.map((supplier) => <tr key={supplier.id}><td><a href={`#/suppliers/${supplier.id}`}>{supplier.supplier_code}</a></td><td>{supplier.name}</td></tr>)}</tbody></table></div>
        : <p>{result.data.total === 0 ? 'No suppliers yet. Create a supplier to start recording purchase orders.' : 'No suppliers on this page. Use Previous to return to earlier records.'}</p>}
      <Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={(next) => navigate(listHash('suppliers', { limit, offset: next }))} />
    </>}
  </section>
}
