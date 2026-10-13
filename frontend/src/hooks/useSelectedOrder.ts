import { useCallback } from 'react'
import { ApiFailure, getPurchaseOrder } from '../api.ts'
import type { PurchaseOrderSummary } from '../types.ts'
import { selectedOrderDetail } from '../selections.ts'
import { useRead } from './useBusiness.ts'

export function useSelectedOrder(selected: PurchaseOrderSummary | null, supplierId?: string) {
  const id = selected?.id
  const load = useCallback((signal: AbortSignal) => id ? getPurchaseOrder(id, { signal }) : Promise.resolve(null), [id])
  const result = useRead(`selected-order-${id ?? 'none'}-${supplierId ?? 'all'}`, load)
  const detail = selectedOrderDetail(selected, result.data, supplierId)
  const mismatch = result.data !== null && detail === null
  return { ...result, data: detail, error: result.error ?? (mismatch ? new ApiFailure('invalid-response', 'The returned order does not match your current selection.') : null) }
}
