import type { OrderParams, PageParams } from './types.ts'
import { isUuid } from './validation.ts'

export const DEFAULT_PAGE: PageParams = { limit: 20, offset: 0 }
export const MAX_OFFSET = 10000
export type Route =
  | { kind: 'status' | 'supplier-new' | 'order-new' | 'not-found' }
  | { kind: 'supplier-list'; page: PageParams }
  | { kind: 'supplier-detail'; id: string; page: PageParams }
  | { kind: 'order-list'; page: OrderParams }
  | { kind: 'order-detail'; id: string }

export function validPage(page: PageParams) {
  return Number.isInteger(page.limit) && page.limit >= 1 && page.limit <= 100 && Number.isInteger(page.offset) && page.offset >= 0 && page.offset <= MAX_OFFSET
}

export function parseHash(hash: string): Route {
  if (hash === '' || hash === '#') return { kind: 'status' }
  const [path, search = '', ...rest] = hash.slice(1).split('?')
  if (!hash.startsWith('#/') || rest.length) return { kind: 'not-found' }
  const query = new URLSearchParams(search)
  if (['/status', '/suppliers/new', '/purchase-orders/new'].includes(path)) {
    if (query.size) return { kind: 'not-found' }
    return { kind: path === '/status' ? 'status' : path === '/suppliers/new' ? 'supplier-new' : 'order-new' }
  }
  const supplierDetail = /^\/suppliers\/([^/]+)$/.exec(path)
  const orderDetail = /^\/purchase-orders\/([^/]+)$/.exec(path)
  if (orderDetail) return isUuid(orderDetail[1]) && !query.size ? { kind: 'order-detail', id: orderDetail[1] } : { kind: 'not-found' }
  if (path !== '/suppliers' && path !== '/purchase-orders' && !supplierDetail) return { kind: 'not-found' }
  if (supplierDetail && !isUuid(supplierDetail[1])) return { kind: 'not-found' }
  const allowed = path === '/purchase-orders' ? ['limit', 'offset', 'supplier_id'] : ['limit', 'offset']
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
  return { kind: 'order-list', page: { ...page, ...(supplierId === null ? {} : { supplier_id: supplierId }) } }
}

export function listHash(path: string, page: OrderParams = DEFAULT_PAGE) {
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) })
  if (page.supplier_id) query.set('supplier_id', page.supplier_id)
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
