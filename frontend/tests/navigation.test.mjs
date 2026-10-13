import assert from 'node:assert/strict'
import { test } from 'node:test'
import { DEFAULT_PAGE, listHash, pagination, parseHash, subscribeHashChange } from '../src/navigation.ts'
import { createRequestScope } from '../src/requestScope.ts'

const id = '10000000-0000-4000-8000-000000000001'
test('empty hashes open Status and only implemented routes are recognized', () => {
  for (const hash of ['', '#', '#/status']) assert.deepEqual(parseHash(hash), { kind: 'status' })
  assert.deepEqual(parseHash('#/suppliers'), { kind: 'supplier-list', page: DEFAULT_PAGE })
  assert.deepEqual(parseHash('#/suppliers/new'), { kind: 'supplier-new' })
  assert.deepEqual(parseHash(`#/suppliers/${id}`), { kind: 'supplier-detail', id, page: DEFAULT_PAGE })
  assert.deepEqual(parseHash('#/purchase-orders'), { kind: 'order-list', page: DEFAULT_PAGE })
  assert.deepEqual(parseHash('#/purchase-orders/new'), { kind: 'order-new' })
  assert.deepEqual(parseHash(`#/purchase-orders/${id}`), { kind: 'order-detail', id })
})
test('list and linked-supplier deep links retain pagination and filters', () => {
  assert.deepEqual(parseHash(listHash('purchase-orders', { limit: 20, offset: 40, supplier_id: id })), { kind: 'order-list', page: { limit: 20, offset: 40, supplier_id: id } })
  assert.deepEqual(parseHash(listHash(`suppliers/${id}`, { limit: 20, offset: 20 })), { kind: 'supplier-detail', id, page: { limit: 20, offset: 20 } })
})
for (const hash of ['#/invoices', '#/deliveries', '#/delivery-receipts', '#/suppliers/bad', '#/purchase-orders/bad', '#page-content', '#/unknown', '#/suppliers/new?offset=1', '#/suppliers?limit=0', '#/suppliers?offset=-1', '#/suppliers?offset=10001', '#/suppliers?limit=101', '#/suppliers?limit=1e1', '#/suppliers?limit=', '#/suppliers?offset=0&offset=20', '#/purchase-orders?supplier_id=bad', '#/suppliers?workspace_id=bad', '#/status?unknown=true']) {
  test(`unknown or invalid route ${hash} has a page-not-found state`, () => assert.equal(parseHash(hash).kind, 'not-found'))
}
test('pagination handles empty lists, previous/next and the offset limit', () => {
  assert.deepEqual(pagination(DEFAULT_PAGE, 0, 0), { previous: 0, next: 20, hasPrevious: false, hasNext: false, label: 'Showing 0 records on this page (0 total)' })
  assert.equal(pagination(DEFAULT_PAGE, 21, 20).hasNext, true)
  assert.equal(pagination({ limit: 20, offset: 20 }, 21, 1).hasPrevious, true)
  assert.equal(pagination({ limit: 20, offset: 20 }, 21, 1).hasNext, false)
  assert.equal(pagination({ limit: 20, offset: 10000 }, 20000, 20).hasNext, false)
})
test('hash subscription reacts to navigation/history events and releases the listener', () => {
  const target = new EventTarget()
  const host = { location: { hash: '#/status' }, addEventListener: target.addEventListener.bind(target), removeEventListener: target.removeEventListener.bind(target) }
  const seen = []
  const release = subscribeHashChange(() => seen.push(parseHash(host.location.hash).kind), host)
  for (const hash of ['#/suppliers', '#/purchase-orders', '#/suppliers', '#/purchase-orders']) {
    host.location.hash = hash
    target.dispatchEvent(new Event('hashchange'))
  }
  assert.deepEqual(seen, ['supplier-list', 'order-list', 'supplier-list', 'order-list'])
  release()
  target.dispatchEvent(new Event('hashchange'))
  assert.equal(seen.length, 4)
})
test('new reads cancel earlier ones and cannot accept their late completion', async () => {
  const scope = createRequestScope()
  const old = scope.start()
  let finishOld
  const oldResult = new Promise((resolve) => { finishOld = resolve })
  const values = []
  const completion = oldResult.then((value) => { if (scope.isCurrent(old)) values.push(value) })
  const current = scope.start()
  assert.equal(old.signal.aborted, true)
  finishOld('obsolete')
  await completion
  if (scope.isCurrent(current)) values.push('current')
  assert.deepEqual(values, ['current'])
})
test('leaving a form prevents a late saved response from redirecting', async () => {
  const scope = createRequestScope()
  const write = scope.start()
  let finish
  const pending = new Promise((resolve) => { finish = resolve })
  let redirected = false
  const completion = pending.then(() => { if (scope.isCurrent(write)) redirected = true })
  scope.cancel()
  finish({ id })
  await completion
  assert.equal(write.signal.aborted, true)
  assert.equal(redirected, false)
  assert.equal(scope.isCurrent(scope.start()), true)
})
