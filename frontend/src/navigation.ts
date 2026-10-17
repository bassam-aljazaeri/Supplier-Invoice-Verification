import type { DeliveryParams, InvoiceParams, OrderParams, PageParams } from './types.ts'
import { isUuid } from './validation.ts'

export const DEFAULT_PAGE: PageParams = { limit: 20, offset: 0 }
export const MAX_OFFSET = 10000
export type Route =
  | { kind: 'status' | 'signin' | 'account' | 'workspace-new' | 'memberships' | 'supplier-new' | 'order-new' | 'delivery-new' | 'invoice-new' | 'not-found' }
  | { kind: 'supplier-list'; page: PageParams }
  | { kind: 'supplier-detail'; id: string; page: PageParams }
  | { kind: 'order-list'; page: OrderParams }
  | { kind: 'order-detail'; id: string }
  | { kind: 'delivery-list'; page: DeliveryParams }
  | { kind: 'delivery-detail'; id: string }
  | { kind: 'invoice-list'; page: InvoiceParams }
  | { kind: 'invoice-detail'; id: string }

export function validPage(page: PageParams) {
  return Number.isInteger(page.limit) && page.limit >= 1 && page.limit <= 100 && Number.isInteger(page.offset) && page.offset >= 0 && page.offset <= MAX_OFFSET
}

export function parseHash(hash: string): Route {
  if (hash === '' || hash === '#') return { kind: 'status' }
  const [path, search = '', ...rest] = hash.slice(1).split('?')
  if (!hash.startsWith('#/') || rest.length) return { kind: 'not-found' }
  const query = new URLSearchParams(search)
  const accountRoutes = { '/signin': 'signin', '/account': 'account', '/workspaces/new': 'workspace-new', '/memberships': 'memberships' } as const
  if (path in accountRoutes) return query.size ? { kind: 'not-found' } : { kind: accountRoutes[path as keyof typeof accountRoutes] }
  if (['/status', '/suppliers/new', '/purchase-orders/new', '/deliveries/new', '/invoices/new'].includes(path)) {
    if (query.size) return { kind: 'not-found' }
    return { kind: path === '/status' ? 'status' : path === '/suppliers/new' ? 'supplier-new' : path === '/purchase-orders/new' ? 'order-new' : path === '/deliveries/new' ? 'delivery-new' : 'invoice-new' }
  }
  const supplierDetail = /^\/suppliers\/([^/]+)$/.exec(path)
  const orderDetail = /^\/purchase-orders\/([^/]+)$/.exec(path)
  if (orderDetail) return isUuid(orderDetail[1]) && !query.size ? { kind: 'order-detail', id: orderDetail[1] } : { kind: 'not-found' }
  const deliveryDetail = /^\/deliveries\/([^/]+)$/.exec(path)
  if (deliveryDetail) return isUuid(deliveryDetail[1]) && !query.size ? { kind: 'delivery-detail', id: deliveryDetail[1] } : { kind: 'not-found' }
  const invoiceDetail = /^\/invoices\/([^/]+)$/.exec(path)
  if (invoiceDetail) return isUuid(invoiceDetail[1]) && !query.size ? { kind: 'invoice-detail', id: invoiceDetail[1] } : { kind: 'not-found' }
  if (!['/suppliers', '/purchase-orders', '/deliveries', '/invoices'].includes(path) && !supplierDetail) return { kind: 'not-found' }
  if (supplierDetail && !isUuid(supplierDetail[1])) return { kind: 'not-found' }
  const allowed = ['limit', 'offset', ...((path === '/purchase-orders' || path === '/invoices') ? ['supplier_id'] : []), ...((path === '/deliveries' || path === '/invoices') ? ['purchase_order_id'] : [])]
  if ([...query.keys()].some((key) => !allowed.includes(key) || query.getAll(key).length !== 1)) return { kind: 'not-found' }
  const limit = query.get('limit') ?? '20'
  const offset = query.get('offset') ?? '0'
  if (!/^[0-9]+$/.test(limit) || !/^[0-9]+$/.test(offset)) return { kind: 'not-found' }
  const page = { limit: Number(limit), offset: Number(offset) }
  if (!validPage(page)) return { kind: 'not-found' }
  if (supplierDetail) return { kind: 'supplier-detail', id: supplierDetail[1], page }
  if (path === '/suppliers') return { kind: 'supplier-list', page }
  const supplierId = query.get('supplier_id')
  if (supplierId !== null && !isUuid(supplierId)) return { kind: 'not-found' }
  const orderId = query.get('purchase_order_id')
  if (orderId !== null && !isUuid(orderId)) return { kind: 'not-found' }
  const filteredPage = { ...page, ...(supplierId === null ? {} : { supplier_id: supplierId }), ...(orderId === null ? {} : { purchase_order_id: orderId }) }
  return { kind: path === '/deliveries' ? 'delivery-list' : path === '/invoices' ? 'invoice-list' : 'order-list', page: filteredPage }
}

export function listHash(path: string, page: InvoiceParams = DEFAULT_PAGE) {
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) })
  if (page.supplier_id) query.set('supplier_id', page.supplier_id)
  if (page.purchase_order_id) query.set('purchase_order_id', page.purchase_order_id)
  return `#/${path}?${query}`
}

export function pagination(page: PageParams, total: number, count: number) {
  return {
    previous: Math.max(0, page.offset - page.limit), next: page.offset + page.limit,
    hasPrevious: page.offset > 0, hasNext: page.offset + page.limit < total && page.offset + page.limit <= MAX_OFFSET,
    label: count ? `Showing ${page.offset + 1}–${page.offset + count} of ${total}` : `Showing 0 records on this page (${total} total)`,
  }
}

type HashHost = { location: { hash: string }; addEventListener: (event: string, listener: () => void) => void; removeEventListener: (event: string, listener: () => void) => void }

export function subscribeHashChange(listener: () => void, host: HashHost = window) {
  host.addEventListener('hashchange', listener)
  return () => host.removeEventListener('hashchange', listener)
}

export function navigate(hash: string) {
  window.location.hash = hash
}

export function safeReturnHash(value: unknown) {
  return typeof value === 'string' && value.startsWith('#/') && !/[\\\r\n]/.test(value) && value.length <= 1024
    && !['not-found', 'signin'].includes(parseHash(value).kind) ? value : '#/account'
}
