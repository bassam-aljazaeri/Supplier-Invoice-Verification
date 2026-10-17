import type { DeliveryParams, DeliveryReceipt, DeliveryReceiptCreate, DeliveryReceiptSummary, ErrorDetail, Invoice, InvoiceCreate, InvoiceParams, InvoiceSummary, OrderParams, PageParams, PurchaseOrder, PurchaseOrderCreate, PurchaseOrderSummary, RecordPage, Supplier, SupplierCreate } from './types.ts'
import { isUuid, MONEY_MAX, PRICE_MAX, QUANTITY_MAX, validDate, validDecimal, validateDelivery, validateInvoice, validateOrder, validateSupplier } from './validation.ts'
import { DEFAULT_PAGE, validPage } from './navigation.ts'

export type FailureKind = 'unauthorized' | 'forbidden' | 'validation' | 'conflict' | 'missing' | 'unavailable' | 'server' | 'network' | 'timeout' | 'cancelled' | 'invalid-response'
export class ApiFailure extends Error {
  kind: FailureKind
  details: ErrorDetail[]
  status?: number
  uncertainWrite: boolean

  constructor(kind: FailureKind, message: string, details: ErrorDetail[] = [], status?: number, uncertainWrite = false) {
    super(message)
    this.name = 'ApiFailure'
    this.kind = kind
    this.details = details
    this.status = status
    this.uncertainWrite = uncertainWrite
  }
}

export type RequestOptions = { signal?: AbortSignal; timeoutMs?: number }
export type PrivateContext = {
  workspaceId: string | null
  accessToken: () => Promise<string>
  onFailure: (status: 401 | 403) => void
}
let context: (PrivateContext & { controller: AbortController; writes: number; uncertain: boolean }) | null = null
let contextVersion = 0
export const privateContextVersion = () => contextVersion
export function configurePrivateRequests(next: PrivateContext | null) {
  const previous = context
  context = next ? { ...next, controller: new AbortController(), writes: 0, uncertain: false } : null
  contextVersion++
  previous?.controller.abort()
  return previous && (previous.writes > 0 || previous.uncertain) ? { workspaceId: previous.workspaceId } : null
}
const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const nullableText = (value: unknown) => value === null || typeof value === 'string'
const recordFields = (value: Record<string, unknown>) => isUuid(value.id) && isUuid(value.workspace_id) && typeof value.created_at === 'string'
const decimalOutput = (value: unknown, scale: number, max: string, positive: boolean) => validDecimal(value, scale, max, positive) && new RegExp(`^[0-9]+\\.[0-9]{${scale}}$`).test(value)

function isSupplier(value: unknown): value is Supplier {
  return object(value) && recordFields(value) && typeof value.supplier_code === 'string' && typeof value.name === 'string' && nullableText(value.notes)
}

function isOrderSummary(value: unknown): value is PurchaseOrderSummary {
  return object(value) && recordFields(value) && isUuid(value.supplier_id) && typeof value.po_number === 'string' && validDate(value.order_date) && value.currency === 'EUR' && nullableText(value.notes) && decimalOutput(value.subtotal, 2, MONEY_MAX, false)
}

function isOrder(value: unknown): value is PurchaseOrder {
  if (!object(value) || !Array.isArray(value.lines)) return false
  const lines: unknown[] = value.lines
  return isOrderSummary(value) && lines.length >= 1 && lines.length <= 100 && lines.every((line, index) => object(line) && recordFields(line) && line.purchase_order_id === value.id && line.workspace_id === value.workspace_id && line.line_no === index + 1 && typeof line.description === 'string' && decimalOutput(line.quantity, 3, QUANTITY_MAX, true) && decimalOutput(line.unit_price, 4, PRICE_MAX, false) && decimalOutput(line.line_total, 2, MONEY_MAX, false))
}

function isDeliverySummary(value: unknown): value is DeliveryReceiptSummary {
  return object(value) && recordFields(value) && isUuid(value.purchase_order_id) && typeof value.receipt_number === 'string' && validDate(value.received_date) && nullableText(value.notes)
}

function isDelivery(value: unknown): value is DeliveryReceipt {
  if (!object(value) || !Array.isArray(value.lines)) return false
  const lines: unknown[] = value.lines
  return isDeliverySummary(value) && lines.length >= 1 && lines.length <= 100 && lines.every((line, index) => object(line) && recordFields(line) && line.workspace_id === value.workspace_id && line.delivery_receipt_id === value.id && line.purchase_order_id === value.purchase_order_id && isUuid(line.purchase_order_line_id) && line.line_no === index + 1 && decimalOutput(line.quantity_received, 3, QUANTITY_MAX, true))
}

function isInvoiceSummary(value: unknown): value is InvoiceSummary {
  return object(value) && recordFields(value) && isUuid(value.supplier_id) && (value.purchase_order_id === null || isUuid(value.purchase_order_id)) && typeof value.invoice_number === 'string' && validDate(value.invoice_date) && (value.due_date === null || (validDate(value.due_date) && value.due_date >= value.invoice_date)) && value.currency === 'EUR' && value.status === 'draft' && nullableText(value.notes) && decimalOutput(value.subtotal, 2, MONEY_MAX, false) && decimalOutput(value.tax_amount, 2, MONEY_MAX, false) && decimalOutput(value.total, 2, MONEY_MAX, false)
}

function isInvoice(value: unknown): value is Invoice {
  if (!object(value) || !Array.isArray(value.lines)) return false
  const lines: unknown[] = value.lines
  return isInvoiceSummary(value) && lines.length >= 1 && lines.length <= 100 && lines.every((line, index) => object(line) && recordFields(line) && line.workspace_id === value.workspace_id && line.invoice_id === value.id && line.line_no === index + 1 && typeof line.description === 'string' && decimalOutput(line.quantity, 3, QUANTITY_MAX, true) && decimalOutput(line.unit_price, 4, PRICE_MAX, false) && decimalOutput(line.line_total, 2, MONEY_MAX, false) && (line.purchase_order_line_id === null || (value.purchase_order_id !== null && isUuid(line.purchase_order_line_id))))
}

function pageOf<T>(isItem: (item: unknown) => item is T) {
  return (value: unknown): value is RecordPage<T> => object(value) && typeof value.limit === 'number' && typeof value.offset === 'number' && validPage({ limit: value.limit, offset: value.offset }) && typeof value.total === 'number' && Number.isSafeInteger(value.total) && value.total >= 0 && Array.isArray(value.items) && value.items.length <= value.limit && value.items.every(isItem)
}

function responseFailure(status: number, body: unknown, post: boolean) {
  const kinds: Record<number, FailureKind> = { 401: 'unauthorized', 403: 'forbidden', 422: 'validation', 404: 'missing', 409: 'conflict', 503: 'unavailable' }
  const messages: Record<number, string> = { 401: 'Your session has ended. Sign in again.', 403: 'Your current permissions do not allow this request.', 422: 'Some fields are invalid.', 404: 'The record or reference was not found.', 409: 'This identifier is already in use.', 503: 'The service is temporarily unavailable.' }
  const kind = kinds[status] ?? 'server'
  const codes: Record<number, string> = { 401: 'unauthorized', 403: 'forbidden', 422: 'validation_error', 404: 'not_found', 409: 'conflict', 503: 'service_unavailable', 500: 'internal_error' }
  const error = object(body) && object(body.error) ? body.error : null
  const envelope = error && typeof codes[status] === 'string' && error.code === codes[status] && typeof error.message === 'string' && Array.isArray(error.details) && error.details.every((detail) => object(detail) && typeof detail.field === 'string' && typeof detail.message === 'string')
  return new ApiFailure(kind, status === 401 || status === 403 ? messages[status] : envelope ? error.message as string : messages[status] ?? 'The server could not complete the request.', envelope ? error.details as ErrorDetail[] : [], status, post && !envelope && status >= 500)
}

export async function privateRequest<T>(path: string, isValue: (value: unknown) => value is T, options: RequestOptions, payload?: unknown, mode: 'business' | 'account' = 'business', method = payload === undefined ? 'GET' : 'POST'): Promise<T> {
  const authority = context
  if (!authority) throw new ApiFailure('unauthorized', 'Sign in before requesting private records.', [], 401)
  if (mode === 'business' && !isUuid(authority.workspaceId)) throw new ApiFailure('forbidden', 'Choose an accessible workspace first.', [], 403)
  if (!path.startsWith('/') || path.startsWith('//') || /[\\\r\n]/.test(path)) throw new ApiFailure('validation', 'Invalid API path.')
  const post = method !== 'GET'
  const timeout = new AbortController()
  const signal = AbortSignal.any([timeout.signal, authority.controller.signal, ...(options.signal ? [options.signal] : [])])
  let dispatched = false
  let countedWrite = false
  const timer = setTimeout(() => timeout.abort(new DOMException('Request timed out', 'TimeoutError')), options.timeoutMs ?? 5000)
  let abortListener: () => void = () => {}
  const interrupted = new Promise<never>((resolve, reject) => {
    void resolve
    abortListener = () => reject(signal.reason)
    signal.addEventListener('abort', abortListener, { once: true })
  })
  try {
    signal.throwIfAborted()
    const operation = (async () => {
      const token = await authority.accessToken()
      signal.throwIfAborted()
      if (context !== authority) throw new DOMException('Obsolete request', 'AbortError')
      if (!token) throw new ApiFailure('unauthorized', 'Sign in again.', [], 401)
      dispatched = true
      if (post) { authority.writes++; countedWrite = true }
      const response = await fetch(`/api${path}`, {
        method, headers: { Accept: 'application/json', Authorization: `Bearer ${token}`, ...(mode === 'business' ? { 'X-Workspace-ID': authority.workspaceId! } : {}), ...(payload !== undefined ? { 'Content-Type': 'application/json' } : {}) },
        cache: 'no-store', credentials: 'omit', redirect: 'error', signal, ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
      })
      signal.throwIfAborted()
      if (method === 'DELETE' && response.status === 204) return undefined as T
      let body: unknown
      try { body = await response.json() } catch {
        if (!response.ok) throw responseFailure(response.status, null, post)
        throw new ApiFailure('invalid-response', 'The response could not be read.', [], response.status, post)
      }
      if (!response.ok) throw responseFailure(response.status, body, post)
      signal.throwIfAborted()
      const expected = method === 'POST' ? 201 : 200
      const belongs = mode !== 'business' || (object(body) && (Array.isArray(body.items) ? body.items.every((item) => object(item) && item.workspace_id === authority.workspaceId) : body.workspace_id === authority.workspaceId))
      if (response.status !== expected || !isValue(body) || !belongs) throw new ApiFailure('invalid-response', 'The server returned an unexpected record format.', [], response.status, post)
      return body
    })()
    return await Promise.race([operation, interrupted])
  } catch (error) {
    if (error instanceof ApiFailure && (error.status === 401 || error.status === 403)) {
      if (countedWrite) { authority.writes--; countedWrite = false }
      if (context === authority && !authority.controller.signal.aborted) authority.onFailure(error.status)
      throw error
    }
    if (signal.aborted) {
      if (post && dispatched) authority.uncertain = true
      const timedOut = signal.reason instanceof DOMException && signal.reason.name === 'TimeoutError'
      throw new ApiFailure(timedOut ? 'timeout' : 'cancelled', timedOut ? 'The request timed out.' : 'The request was interrupted.', [], undefined, post && dispatched)
    }
    if (error instanceof ApiFailure) { if (error.uncertainWrite) authority.uncertain = true; throw error }
    if (post && dispatched) authority.uncertain = true
    throw new ApiFailure('network', 'Could not reach the service. Check your connection and service status.', [], undefined, post && dispatched)
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort', abortListener)
    if (countedWrite) authority.writes--
  }
}

const request = privateRequest

function queryFor(page: PageParams) {
  if (!validPage(page)) throw new ApiFailure('validation', 'Invalid page limits.')
  return new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) })
}

export function getSuppliers(page: PageParams = DEFAULT_PAGE, options: RequestOptions = {}) {
  return request(`/suppliers?${queryFor(page)}`, pageOf(isSupplier), options)
}
export function getSupplier(id: string, options: RequestOptions = {}) {
  return request(`/suppliers/${encodeURIComponent(id)}`, isSupplier, options)
}
export function getPurchaseOrders(page: OrderParams = DEFAULT_PAGE, options: RequestOptions = {}) {
  const query = queryFor(page)
  if (page.supplier_id !== undefined) {
    if (!isUuid(page.supplier_id)) throw new ApiFailure('validation', 'Choose an available supplier.')
    query.set('supplier_id', page.supplier_id)
  }
  return request(`/purchase-orders?${query}`, pageOf(isOrderSummary), options)
}
export function getPurchaseOrder(id: string, options: RequestOptions = {}) {
  return request(`/purchase-orders/${encodeURIComponent(id)}`, isOrder, options)
}
export function createSupplier(input: SupplierCreate, options: RequestOptions = {}) {
  const details = validateSupplier(input)
  if (details.length) return Promise.reject(new ApiFailure('validation', 'Some fields are invalid.', details))
  return request('/suppliers', isSupplier, options, { supplier_code: input.supplier_code.trim(), name: input.name.trim(), notes: input.notes?.trim() || null })
}
export function createPurchaseOrder(input: PurchaseOrderCreate, options: RequestOptions = {}) {
  const details = validateOrder(input)
  if (details.length) return Promise.reject(new ApiFailure('validation', 'Some fields are invalid.', details))
  return request('/purchase-orders', isOrder, options, {
    supplier_id: input.supplier_id, po_number: input.po_number.trim(), order_date: input.order_date, currency: 'EUR', notes: input.notes?.trim() || null,
    lines: input.lines.map((line) => ({ description: line.description.trim(), quantity: line.quantity, unit_price: line.unit_price })),
  })
}

export function getDeliveryReceipts(page: DeliveryParams = DEFAULT_PAGE, options: RequestOptions = {}) {
  const query = queryFor(page)
  if (page.purchase_order_id !== undefined) {
    if (!isUuid(page.purchase_order_id)) throw new ApiFailure('validation', 'Choose an available purchase order.')
    query.set('purchase_order_id', page.purchase_order_id)
  }
  return request(`/delivery-receipts?${query}`, pageOf(isDeliverySummary), options)
}
export function getDeliveryReceipt(id: string, options: RequestOptions = {}) {
  return request(`/delivery-receipts/${encodeURIComponent(id)}`, isDelivery, options)
}
export function createDeliveryReceipt(input: DeliveryReceiptCreate, options: RequestOptions = {}) {
  const details = validateDelivery(input)
  if (details.length) return Promise.reject(new ApiFailure('validation', 'Some fields are invalid.', details))
  return request('/delivery-receipts', isDelivery, options, {
    purchase_order_id: input.purchase_order_id, receipt_number: input.receipt_number.trim(), received_date: input.received_date, notes: input.notes?.trim() || null,
    lines: input.lines.map((line) => ({ purchase_order_line_id: line.purchase_order_line_id, quantity_received: line.quantity_received })),
  })
}
export function getInvoices(page: InvoiceParams = DEFAULT_PAGE, options: RequestOptions = {}) {
  const query = queryFor(page)
  for (const field of ['supplier_id', 'purchase_order_id'] as const) {
    if (page[field] !== undefined) {
      if (!isUuid(page[field])) throw new ApiFailure('validation', 'Choose an available supplier or purchase order.')
      query.set(field, page[field])
    }
  }
  return request(`/invoices?${query}`, pageOf(isInvoiceSummary), options)
}
export function getInvoice(id: string, options: RequestOptions = {}) {
  return request(`/invoices/${encodeURIComponent(id)}`, isInvoice, options)
}
export function createInvoice(input: InvoiceCreate, options: RequestOptions = {}) {
  const details = validateInvoice(input)
  if (details.length) return Promise.reject(new ApiFailure('validation', 'Some fields are invalid.', details))
  return request('/invoices', isInvoice, options, {
    supplier_id: input.supplier_id, purchase_order_id: input.purchase_order_id ?? null, invoice_number: input.invoice_number.trim(), invoice_date: input.invoice_date,
    due_date: input.due_date ?? null, currency: 'EUR', tax_amount: input.tax_amount, notes: input.notes?.trim() || null,
    lines: input.lines.map((line) => ({ description: line.description.trim(), quantity: line.quantity, unit_price: line.unit_price, purchase_order_line_id: line.purchase_order_line_id ?? null })),
  })
}
