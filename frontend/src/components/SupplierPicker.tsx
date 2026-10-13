import { useCallback, useState } from 'react'
import { getSuppliers } from '../api.ts'
import type { ErrorDetail, Supplier } from '../types.ts'
import { fieldError } from '../validation.ts'
import { useRead } from '../hooks/useBusiness.ts'
import Pagination from './Pagination.tsx'
import RequestState from './RequestState.tsx'

export default function SupplierPicker({ selected, onSelect, details, documentName = 'purchase order' }: { selected: Supplier | null; onSelect: (supplier: Supplier) => void; details: ErrorDetail[]; documentName?: string }) {
  const [offset, setOffset] = useState(0)
  const load = useCallback((signal: AbortSignal) => getSuppliers({ limit: 20, offset }, { signal }), [offset])
  const result = useRead(`supplier-picker-${offset}`, load)
  const error = fieldError(details, 'supplier_id')
  return <fieldset className="supplier-picker" data-field="supplier_id" tabIndex={-1} aria-describedby={error ? 'supplier-error' : undefined} aria-invalid={!!error}>
    <legend>Supplier</legend>
    <p className="hint">Choose a supplier by code and name. Use Previous and Next to browse all available pages.</p>
    {selected && <p className="selected-supplier">Selected: <strong>{selected.supplier_code} — {selected.name}</strong></p>}
    {error && <p className="field-error" id="supplier-error">{error}</p>}
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {result.data && <>
      {result.data.items.length ? <ul className="supplier-options">{result.data.items.map((supplier) => <li key={supplier.id}>
        <label htmlFor={`supplier-${supplier.id}`}><input id={`supplier-${supplier.id}`} type="radio" name="supplier_id" value={supplier.id} checked={selected?.id === supplier.id} onChange={() => onSelect(supplier)} /> <span>{supplier.supplier_code} — {supplier.name}</span></label>
      </li>)}</ul> : <p>{result.data.total === 0 ? `Create a supplier first before saving a ${documentName}.` : 'No suppliers on this page. Use Previous to return to earlier records.'}</p>}
      <Pagination page={result.data} total={result.data.total} count={result.data.items.length} onPage={setOffset} />
    </>}
    <a href="#/suppliers/new">Create a supplier</a>
  </fieldset>
}
