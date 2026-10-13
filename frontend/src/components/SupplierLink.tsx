import { useCallback } from 'react'
import { getSupplier } from '../api.ts'
import { useRead } from '../hooks/useBusiness.ts'
import RequestState from './RequestState.tsx'

export default function SupplierLink({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getSupplier(id, { signal }), [id])
  const result = useRead(`linked-supplier-${id}`, load)
  return <div><RequestState loading={result.loading} error={result.error} retry={result.retry} />
    <a href={`#/suppliers/${id}`}>{result.data ? `${result.data.supplier_code} — ${result.data.name}` : 'View supplier'}</a>
  </div>
}
