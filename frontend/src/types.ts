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
export type LineDraft = OrderLineCreate & { key: string; purchase_order_line_id?: string | null }
export type OrderDraft = {
  supplier: Supplier | null; po_number: string; order_date: string; notes: string; lines: LineDraft[]
}

export type DeliveryLineCreate = { purchase_order_line_id: string; quantity_received: string }
export type DeliveryReceiptCreate = {
  purchase_order_id: string; receipt_number: string; received_date: string
  notes?: string | null; lines: DeliveryLineCreate[]
}
export type DeliveryLine = RecordFields & DeliveryLineCreate & {
  delivery_receipt_id: string; purchase_order_id: string; line_no: number
}
export type DeliveryReceiptSummary = RecordFields & {
  purchase_order_id: string; receipt_number: string; received_date: string; notes: string | null
}
export type DeliveryReceipt = DeliveryReceiptSummary & { lines: DeliveryLine[] }
export type DeliveryParams = PageParams & { purchase_order_id?: string }
export type DeliveryLineDraft = DeliveryLineCreate & { key: string }
export type DeliveryDraft = {
  order: PurchaseOrderSummary | null; receipt_number: string; received_date: string; notes: string; lines: DeliveryLineDraft[]
}
export type InvoiceLineCreate = OrderLineCreate & { purchase_order_line_id?: string | null }
export type InvoiceCreate = {
  supplier_id: string; purchase_order_id?: string | null; invoice_number: string
  invoice_date: string; due_date?: string | null; currency: 'EUR'; tax_amount: string
  notes?: string | null; lines: InvoiceLineCreate[]
}
export type InvoiceLine = RecordFields & OrderLineCreate & {
  invoice_id: string; line_no: number; line_total: string; purchase_order_line_id: string | null
}
export type InvoiceSummary = RecordFields & {
  supplier_id: string; purchase_order_id: string | null; invoice_number: string
  invoice_date: string; due_date: string | null; currency: 'EUR'; status: 'draft'
  notes: string | null; subtotal: string; tax_amount: string; total: string
}
export type Invoice = InvoiceSummary & { lines: InvoiceLine[] }
export type InvoiceParams = PageParams & { supplier_id?: string; purchase_order_id?: string }
export type InvoiceDraft = {
  supplier: Supplier | null; order: PurchaseOrderSummary | null; invoice_number: string
  invoice_date: string; due_date: string; tax_amount: string; notes: string; lines: LineDraft[]
}
