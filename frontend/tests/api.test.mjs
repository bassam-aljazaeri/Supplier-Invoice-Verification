import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'
import { configurePrivateRequests } from '../src/api.ts'
import { createPurchaseOrder, createSupplier, getPurchaseOrder, getPurchaseOrders, getSupplier, getSuppliers } from '../src/api.ts'

// Fictional response IDs only; these tests never contact a database.
const supplierId = '10000000-0000-4000-8000-000000000001'
const orderId = '20000000-0000-4000-8000-000000000001'
const workspaceId = '00000000-0000-4000-8000-000000000001'
beforeEach(() => configurePrivateRequests({ workspaceId, accessToken: async () => 'synthetic-access-token', onFailure: () => {} }))
afterEach(() => configurePrivateRequests(null))
const savedSupplier = { id: supplierId, workspace_id: workspaceId, created_at: '2026-10-13T09:00:00Z', supplier_code: 'SYNTHETIC', name: 'Fictional supplier', notes: null }
const inputOrder = { supplier_id: supplierId, po_number: 'PO-SYNTHETIC', order_date: '2026-10-13', currency: 'EUR', notes: null, lines: [{ description: 'Keyboard', quantity: '10.000', unit_price: '25.0000' }] }
const savedOrder = {
  id: orderId, workspace_id: workspaceId, created_at: '2026-10-13T09:00:00Z',
  supplier_id: supplierId, po_number: 'PO-SYNTHETIC', order_date: '2026-10-13', currency: 'EUR', notes: null, subtotal: '250.00',
  lines: [{ id: '21000000-0000-4000-8000-000000000001', workspace_id: workspaceId, created_at: '2026-10-13T09:00:00Z', purchase_order_id: orderId, line_no: 1, description: 'Keyboard', quantity: '10.000', unit_price: '25.0000', line_total: '250.00' }],
}
const { lines: omittedLines, ...summary } = savedOrder
void omittedLines
const page = (items, limit = 20, offset = 0, total = items.length) => ({ items, limit, offset, total })
const envelope = (code, details = []) => ({ error: { code, message: 'Constant business message.', details } })

function waitForAbort(signal) {
  return new Promise((resolve, reject) => {
    void resolve
    if (signal.aborted) reject(signal.reason)
    else signal.addEventListener('abort', () => reject(signal.reason), { once: true })
  })
}

test('supplier requests use the proxy and only accepted fields', async (t) => {
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.equal(path, '/api/suppliers')
    assert.equal(options.method, 'POST')
    assert.equal(options.cache, 'no-store')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.equal(options.headers.Accept, 'application/json')
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-token')
    assert.equal(options.headers['X-Workspace-ID'], workspaceId)
    assert.deepEqual(JSON.parse(options.body), { supplier_code: 'SYNTHETIC', name: 'Fictional supplier', notes: null })
    return Response.json(savedSupplier, { status: 201 })
  })
  assert.deepEqual(await createSupplier({ supplier_code: ' SYNTHETIC ', name: ' Fictional supplier ', notes: ' ', workspace_id: 'must-not-send', id: 'must-not-send' }), savedSupplier)
})

test('nested order requests retain exact strings and discard draft/server fields', async (t) => {
  const payload = { ...inputOrder, subtotal: 'untrusted', id: 'untrusted', lines: inputOrder.lines.map((line) => ({ ...line, key: 'local-key', line_total: 'untrusted', line_no: 1 })) }
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.equal(path, '/api/purchase-orders')
    assert.deepEqual(JSON.parse(options.body), inputOrder)
    return Response.json(savedOrder, { status: 201 })
  })
  const saved = await createPurchaseOrder(payload)
  assert.equal(saved.id, orderId)
  assert.equal(saved.subtotal, '250.00')
  assert.equal(saved.lines[0].quantity, '10.000')
  assert.equal(saved.lines[0].unit_price, '25.0000')
  assert.equal(saved.lines[0].line_total, '250.00')
  assert.deepEqual(payload.lines[0].key, 'local-key')
})

test('paginated reads and supplier filters preserve query limits and counts', async (t) => {
  const paths = []
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    paths.push(path)
    assert.equal(options.method, 'GET')
    assert.equal(options.cache, 'no-store')
    return Response.json(path.includes('/purchase-orders') ? page([summary], 20, 20, 42) : page([savedSupplier], 20, 20, 42))
  })
  assert.equal((await getSuppliers({ limit: 20, offset: 20 })).total, 42)
  assert.equal((await getPurchaseOrders({ limit: 20, offset: 20, supplier_id: supplierId })).items[0].subtotal, '250.00')
  assert.deepEqual(paths, ['/api/suppliers?limit=20&offset=20', `/api/purchase-orders?limit=20&offset=20&supplier_id=${supplierId}`])
})

test('supplier and full-order detail reads retain saved fields', async (t) => {
  t.mock.method(globalThis, 'fetch', async (path) => Response.json(path.includes('purchase-orders') ? savedOrder : savedSupplier))
  assert.deepEqual(await getSupplier(supplierId), savedSupplier)
  assert.deepEqual(await getPurchaseOrder(orderId), savedOrder)
})

for (const [status, code, kind] of [[422, 'validation_error', 'validation'], [404, 'not_found', 'missing'], [409, 'conflict', 'conflict'], [503, 'service_unavailable', 'unavailable'], [500, 'internal_error', 'server']]) {
  test(`maps HTTP ${status} to ${kind} using the business envelope`, async (t) => {
    const details = [{ field: 'lines[0].quantity', message: 'Enter a positive decimal string.' }]
    t.mock.method(globalThis, 'fetch', async () => Response.json(envelope(code, details), { status }))
    await assert.rejects(createPurchaseOrder(inputOrder), (error) => {
      assert.equal(error.kind, kind)
      assert.equal(error.status, status)
      assert.equal(error.uncertainWrite, false)
      assert.deepEqual(error.details, details)
      return true
    })
  })
}

test('unexpected error responses do not expose proxy HTML or raw exceptions', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>private database exception</html>', { status: 502 }))
  await assert.rejects(createPurchaseOrder(inputOrder), (error) => {
    assert.equal(error.kind, 'server')
    assert.equal(error.uncertainWrite, true)
    assert.equal(error.message.includes('private'), false)
    return true
  })
})

test('numeric or malformed saved decimals fail instead of being converted', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ ...savedOrder, subtotal: 250 }, { status: 201 }))
  await assert.rejects(createPurchaseOrder(inputOrder), (error) => error.kind === 'invalid-response' && error.uncertainWrite)
  t.mock.method(globalThis, 'fetch', async () => Response.json({ ...savedOrder, lines: [{ ...savedOrder.lines[0], quantity: '10' }] }))
  await assert.rejects(getPurchaseOrder(orderId), (error) => error.kind === 'invalid-response' && !error.uncertainWrite)
})

test('bad nested decimal input never dispatches a POST', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(savedOrder, { status: 201 }) })
  await assert.rejects(createPurchaseOrder({ ...inputOrder, lines: [{ ...inputOrder.lines[0], quantity: 10 }] }), (error) => error.kind === 'validation' && !error.uncertainWrite && error.details[0].field === 'lines[0].quantity')
  assert.equal(calls, 0)
})

test('bad pagination or malformed filters are rejected before fetching', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(page([])) })
  for (const params of [{ limit: 101, offset: 0 }, { limit: 20, offset: 10001 }, { limit: 0, offset: 0 }]) assert.throws(() => getSuppliers(params), (error) => error.kind === 'validation')
  assert.throws(() => getPurchaseOrders({ limit: 20, offset: 0, supplier_id: 'bad' }), (error) => error.kind === 'validation')
  assert.equal(calls, 0)
})

test('network failures leave writes uncertain without automatically retrying', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; throw new TypeError('raw-private-network-detail') })
  const input = structuredClone(inputOrder)
  await assert.rejects(createPurchaseOrder(input), (error) => error.kind === 'network' && error.uncertainWrite && !error.message.includes('raw-private'))
  assert.equal(calls, 1)
  assert.deepEqual(input, inputOrder)
  await assert.rejects(getSuppliers(), (error) => error.kind === 'network' && !error.uncertainWrite)
})

test('header timeout bounds a read and distinguishes it from network failure', { timeout: 1000 }, async (t) => {
  t.mock.method(globalThis, 'fetch', (path, { signal }) => waitForAbort(signal))
  await assert.rejects(getSuppliers(undefined, { timeoutMs: 15 }), (error) => error.kind === 'timeout' && !error.uncertainWrite)
})

test('body timeout leaves a dispatched write uncertain and retains the input', { timeout: 1000 }, async (t) => {
  let calls = 0
  let bodyRead = false
  t.mock.method(globalThis, 'fetch', async (path, { signal }) => {
    calls++
    return { ok: true, status: 201, json: () => { bodyRead = true; return waitForAbort(signal) } }
  })
  const input = structuredClone(inputOrder)
  await assert.rejects(createPurchaseOrder(input, { timeoutMs: 15 }), (error) => error.kind === 'timeout' && error.uncertainWrite)
  assert.equal(bodyRead, true)
  assert.equal(calls, 1)
  assert.deepEqual(input, inputOrder)
})

test('a body ignoring abort still cannot bypass the duration bound', { timeout: 1000 }, async (t) => {
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, status: 200, json: () => new Promise(() => {}) }))
  await assert.rejects(getSuppliers(undefined, { timeoutMs: 15 }), (error) => error.kind === 'timeout')
})

for (const write of [false, true]) {
  test(`cancels an obsolete ${write ? 'write (uncertain)' : 'read'} during body reading`, async (t) => {
    const controller = new AbortController()
    let started
    const bodyStarted = new Promise((resolve) => { started = resolve })
    t.mock.method(globalThis, 'fetch', async (path, { signal }) => ({ ok: true, status: write ? 201 : 200, json: () => { started(); return waitForAbort(signal) } }))
    const pending = write ? createPurchaseOrder(inputOrder, { signal: controller.signal }) : getSuppliers(undefined, { signal: controller.signal })
    await bodyStarted
    controller.abort()
    await assert.rejects(pending, (error) => error.kind === 'cancelled' && error.uncertainWrite === write)
  })
}

test('an already-aborted save is never dispatched and is not treated as saved', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(savedOrder, { status: 201 }) })
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(createPurchaseOrder(inputOrder, { signal: controller.signal }), (error) => error.kind === 'cancelled' && !error.uncertainWrite)
  assert.equal(calls, 0)
})

test('a later explicit read can recover after a failed request', async (t) => {
  let available = false
  t.mock.method(globalThis, 'fetch', async () => { if (!available) throw new TypeError('offline'); return Response.json(page([savedSupplier])) })
  await assert.rejects(getSuppliers(), (error) => error.kind === 'network')
  available = true
  assert.equal((await getSuppliers()).items[0].id, supplierId)
})
