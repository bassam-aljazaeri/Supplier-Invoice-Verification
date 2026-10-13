import type { ErrorDetail, OrderParams, PageParams, PurchaseOrder, PurchaseOrderCreate, PurchaseOrderSummary, RecordPage, Supplier, SupplierCreate } from './types.ts'
import { isUuid, MONEY_MAX, PRICE_MAX, QUANTITY_MAX, validDate, validDecimal, validateOrder, validateSupplier } from './validation.ts'
import { DEFAULT_PAGE, validPage } from './navigation.ts'

export type FailureKind = 'validation' | 'conflict' | 'missing' | 'unavailable' | 'server' | 'network' | 'timeout' | 'cancelled' | 'invalid-response'
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

function pageOf<T>(isItem: (item: unknown) => item is T) {
  return (value: unknown): value is RecordPage<T> => object(value) && typeof value.limit === 'number' && typeof value.offset === 'number' && validPage({ limit: value.limit, offset: value.offset }) && typeof value.total === 'number' && Number.isSafeInteger(value.total) && value.total >= 0 && Array.isArray(value.items) && value.items.length <= value.limit && value.items.every(isItem)
}

function responseFailure(status: number, body: unknown, post: boolean) {
  const kinds: Record<number, FailureKind> = { 422: 'validation', 404: 'missing', 409: 'conflict', 503: 'unavailable' }
  const messages: Record<number, string> = { 422: 'Some fields are invalid.', 404: 'The record or reference was not found.', 409: 'This identifier is already in use.', 503: 'The service is temporarily unavailable.' }
  const kind = kinds[status] ?? 'server'
  const codes: Record<number, string> = { 422: 'validation_error', 404: 'not_found', 409: 'conflict', 503: 'service_unavailable', 500: 'internal_error' }
  const error = object(body) && object(body.error) ? body.error : null
  const envelope = error && typeof codes[status] === 'string' && error.code === codes[status] && typeof error.message === 'string' && Array.isArray(error.details) && error.details.every((detail) => object(detail) && typeof detail.field === 'string' && typeof detail.message === 'string')
  return new ApiFailure(kind, envelope ? error.message as string : messages[status] ?? 'The server could not complete the request.', envelope ? error.details as ErrorDetail[] : [], status, post && !envelope && status >= 500)
}

async function request<T>(path: string, isValue: (value: unknown) => value is T, options: RequestOptions, payload?: unknown): Promise<T> {
  const post = payload !== undefined
  const timeout = new AbortController()
  const signal = options.signal ? AbortSignal.any([timeout.signal, options.signal]) : timeout.signal
  let dispatched = false
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
      dispatched = true
      const response = await fetch(`/api${path}`, {
        method: post ? 'POST' : 'GET', headers: { Accept: 'application/json', ...(post ? { 'Content-Type': 'application/json' } : {}) },
        cache: 'no-store', signal, ...(post ? { body: JSON.stringify(payload) } : {}),
      })
      let body: unknown
      try { body = await response.json() } catch {
        if (!response.ok) throw responseFailure(response.status, null, post)
        throw new ApiFailure('invalid-response', 'The response could not be read.', [], response.status, post)
      }
      if (!response.ok) throw responseFailure(response.status, body, post)
      if (response.status !== (post ? 201 : 200) || !isValue(body)) throw new ApiFailure('invalid-response', 'The server returned an unexpected record format.', [], response.status, post)
      return body
    })()
    return await Promise.race([operation, interrupted])
  } catch (error) {
    if (signal.aborted) {
      const timedOut = signal.reason instanceof DOMException && signal.reason.name === 'TimeoutError'
      throw new ApiFailure(timedOut ? 'timeout' : 'cancelled', timedOut ? 'The request timed out.' : 'The request was interrupted.', [], undefined, post && dispatched)
    }
    if (error instanceof ApiFailure) throw error
    throw new ApiFailure('network', 'Could not reach the service. Check your connection and service status.', [], undefined, post && dispatched)
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort', abortListener)
  }
}

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
