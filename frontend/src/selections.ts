import type { DeliveryDraft, InvoiceDraft, PurchaseOrder, PurchaseOrderSummary, Supplier } from './types.ts'

export function selectDeliveryOrder(draft: DeliveryDraft, order: PurchaseOrderSummary | null): DeliveryDraft {
  return { ...draft, order, lines: draft.order?.id === order?.id ? draft.lines : [] }
}

export function selectDeliveryLine(draft: DeliveryDraft, lineId: string, selected: boolean): DeliveryDraft {
  if (!draft.order) return draft
  if (!selected) return { ...draft, lines: draft.lines.filter((line) => line.purchase_order_line_id !== lineId) }
  if (draft.lines.some((line) => line.purchase_order_line_id === lineId) || draft.lines.length >= 100) return draft
  return { ...draft, lines: [...draft.lines, { key: crypto.randomUUID(), purchase_order_line_id: lineId, quantity_received: '' }] }
}

export function selectInvoiceSupplier(draft: InvoiceDraft, supplier: Supplier | null): InvoiceDraft {
  if (draft.supplier?.id === supplier?.id) return { ...draft, supplier }
  return { ...draft, supplier, order: null, lines: draft.lines.map((line) => ({ ...line, purchase_order_line_id: null })) }
}

export function selectInvoiceOrder(draft: InvoiceDraft, selected: PurchaseOrderSummary | null): InvoiceDraft {
  const order = selected?.supplier_id === draft.supplier?.id ? selected : null
  if (draft.order?.id === order?.id) return { ...draft, order }
  return { ...draft, order, lines: draft.lines.map((line) => ({ ...line, purchase_order_line_id: null })) }
}

export function selectedOrderDetail(selected: PurchaseOrderSummary | null, received: PurchaseOrder | null, supplierId?: string): PurchaseOrder | null {
  return selected && received && selected.id === received.id && selected.supplier_id === received.supplier_id && (supplierId === undefined || received.supplier_id === supplierId) ? received : null
}
