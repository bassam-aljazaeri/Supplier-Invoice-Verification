// Decimal quantities, prices and amounts remain strings throughout the website.
export type RecordFields = { id: string; workspace_id: string; created_at: string }
export type SupplierCreate = { supplier_code: string; name: string; notes?: string | null }
export type Supplier = RecordFields & SupplierCreate & { notes: string | null }
export type OrderLineCreate = { description: string; quantity: string; unit_price: string }
export type PurchaseOrderCreate = {
  supplier_id: string; po_number: string; order_date: string; currency: 'EUR'
  notes?: string | null; lines: OrderLineCreate[]
}
export type OrderLine = RecordFields & OrderLineCreate & {
  purchase_order_id: string; line_no: number; line_total: string
}
export type PurchaseOrderSummary = RecordFields & {
  supplier_id: string; po_number: string; order_date: string; currency: 'EUR'
  notes: string | null; subtotal: string
}
export type PurchaseOrder = PurchaseOrderSummary & { lines: OrderLine[] }
export type PageParams = { limit: number; offset: number }
export type OrderParams = PageParams & { supplier_id?: string }
export type RecordPage<T> = PageParams & { items: T[]; total: number }
export type ErrorDetail = { field: string; message: string }
export type SupplierDraft = { supplier_code: string; name: string; notes: string }
export type LineDraft = OrderLineCreate & { key: string }
export type OrderDraft = {
  supplier: Supplier | null; po_number: string; order_date: string; notes: string; lines: LineDraft[]
}
