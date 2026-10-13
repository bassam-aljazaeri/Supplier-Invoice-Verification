import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createDeliveryReceipt, createInvoice, getDeliveryReceipt, getDeliveryReceipts, getInvoice, getInvoices } from '../src/api.ts'
import { deliveryPayload, invoicePayload, MONEY_MAX, newDeliveryDraft, newInvoiceDraft, validateDelivery, validateInvoice } from '../src/validation.ts'
import { selectDeliveryLine, selectDeliveryOrder, selectInvoiceOrder, selectInvoiceSupplier, selectedOrderDetail } from '../src/selections.ts'
import { createRequestScope } from '../src/requestScope.ts'

// Fictional response fixtures only. Every request is mocked; no database is contacted.
const supplierId = '10000000-0000-4000-8000-000000000011'
const otherSupplierId = '10000000-0000-4000-8000-000000000012'
const orderId = '20000000-0000-4000-8000-000000000011'
const otherOrderId = '20000000-0000-4000-8000-000000000012'
const orderLineId = '21000000-0000-4000-8000-000000000011'
const secondOrderLineId = '21000000-0000-4000-8000-000000000012'
const receiptId = '30000000-0000-4000-8000-000000000011'
const invoiceId = '40000000-0000-4000-8000-000000000011'
const common = { workspace_id: '00000000-0000-4000-8000-000000000001', created_at: '2026-10-13T09:00:00Z' }
const supplier = { ...common, id: supplierId, supplier_code: 'SYNTHETIC-OFFICE', name: 'Fictional Office Supplier', notes: null }
const otherSupplier = { ...supplier, id: otherSupplierId, supplier_code: 'SYNTHETIC-OTHER' }
const orderSummary = { ...common, id: orderId, supplier_id: supplierId, po_number: 'PO-SYNTHETIC-11', order_date: '2026-10-13', currency: 'EUR', notes: null, subtotal: '260.00' }
const order = { ...orderSummary, lines: [
  { ...common, id: orderLineId, purchase_order_id: orderId, line_no: 1, description: 'Keyboard', quantity: '10.000', unit_price: '25.0000', line_total: '250.00' },
  { ...common, id: secondOrderLineId, purchase_order_id: orderId, line_no: 2, description: 'Mouse', quantity: '1.000', unit_price: '10.0000', line_total: '10.00' },
] }
const otherOrder = { ...orderSummary, id: otherOrderId, po_number: 'PO-SYNTHETIC-12' }
const deliveryInput = { purchase_order_id: orderId, receipt_number: 'DR-SYNTHETIC-11', received_date: '2026-10-14', notes: null, lines: [{ purchase_order_line_id: orderLineId, quantity_received: '8.000' }] }
const receiptSummary = { ...common, id: receiptId, purchase_order_id: orderId, receipt_number: deliveryInput.receipt_number, received_date: deliveryInput.received_date, notes: null }
const receipt = { ...receiptSummary, lines: [{ ...common, id: '31000000-0000-4000-8000-000000000011', delivery_receipt_id: receiptId, purchase_order_id: orderId, purchase_order_line_id: orderLineId, line_no: 1, quantity_received: '8.000' }] }
const invoiceInput = { supplier_id: supplierId, purchase_order_id: orderId, invoice_number: 'INV-SYNTHETIC-11', invoice_date: '2026-10-15', due_date: '2026-11-14', currency: 'EUR', tax_amount: '12.34', notes: null, lines: [{ description: 'Keyboard', quantity: '10.000', unit_price: '25.0000', purchase_order_line_id: orderLineId }] }
const invoiceSummary = { ...common, id: invoiceId, supplier_id: supplierId, purchase_order_id: orderId, invoice_number: invoiceInput.invoice_number, invoice_date: invoiceInput.invoice_date, due_date: invoiceInput.due_date, currency: 'EUR', status: 'draft', notes: null, subtotal: '250.00', tax_amount: '12.34', total: '262.34' }
const invoice = { ...invoiceSummary, lines: [{ ...common, id: '41000000-0000-4000-8000-000000000011', invoice_id: invoiceId, line_no: 1, description: 'Keyboard', quantity: '10.000', unit_price: '25.0000', line_total: '250.00', purchase_order_line_id: orderLineId }] }
const page = (items, limit = 20, offset = 0, total = items.length) => ({ items, limit, offset, total })
const envelope = (code, details = []) => ({ error: { code, message: 'Constant business message.', details } })
const fields = (details) => details.map((detail) => detail.field)
const deliveryDraft = () => ({ order: orderSummary, receipt_number: ' DR-SYNTHETIC-11 ', received_date: '2026-10-14', notes: ' ', lines: [{ key: 'delivery-local', purchase_order_line_id: orderLineId, quantity_received: '8.000' }] })
const invoiceDraft = () => ({ supplier, order: orderSummary, invoice_number: ' INV-SYNTHETIC-11 ', invoice_date: '2026-10-15', due_date: '2026-11-14', tax_amount: '12.34', notes: ' ', lines: [{ key: 'invoice-local', description: ' Keyboard ', quantity: '10.000', unit_price: '25.0000', purchase_order_line_id: orderLineId }] })

function waitForAbort(signal) {
  return new Promise((resolve, reject) => {
    void resolve
    if (signal.aborted) reject(signal.reason)
    else signal.addEventListener('abort', () => reject(signal.reason), { once: true })
  })
}

test('delivery and invoice draft payloads contain only accepted fields and preserve exact strings', () => {
  const delivery = { ...deliveryDraft(), id: 'untrusted', workspace_id: 'untrusted', lines: [{ ...deliveryDraft().lines[0], line_no: 1, purchase_order_id: 'untrusted' }] }
  const bill = { ...invoiceDraft(), status: 'approved', subtotal: 'untrusted', total: 'untrusted', lines: [{ ...invoiceDraft().lines[0], line_total: 'untrusted', purchase_order_id: 'untrusted' }] }
  assert.deepEqual(deliveryPayload(delivery), deliveryInput)
  assert.deepEqual(invoicePayload(bill), invoiceInput)
  assert.equal(delivery.lines[0].key, 'delivery-local')
  assert.equal(bill.lines[0].description, ' Keyboard ')
  assert.equal(bill.tax_amount, '12.34')
})

test('new invoice requires explicit tax and new delivery has no inferred received lines', () => {
  const draft = newInvoiceDraft()
  assert.equal(draft.tax_amount, '')
  assert.equal(draft.supplier, null)
  assert.equal(draft.order, null)
  assert.equal(draft.lines.length, 1)
  assert.equal(draft.lines[0].purchase_order_line_id ?? null, null)
  assert.equal(fields(validateInvoice(invoicePayload(draft))).includes('tax_amount'), true)
  const delivery = newDeliveryDraft()
  assert.equal(delivery.order, null)
  assert.equal(delivery.lines.length, 0)
})

test('invoice payload supports no order, no due date, and explicitly unmapped lines', () => {
  const draft = invoiceDraft()
  draft.order = null
  draft.due_date = ''
  draft.lines[0].purchase_order_line_id = null
  const input = invoicePayload(draft)
  assert.equal(input.purchase_order_id, null)
  assert.equal(input.due_date, null)
  assert.equal(input.lines[0].purchase_order_line_id, null)
  assert.deepEqual(validateInvoice(input), [])
  assert.deepEqual(validateInvoice({ ...input, purchase_order_id: orderId }, order), [])
})

test('changing delivery order clears selected lines but preserves typed header fields', () => {
  const draft = deliveryDraft()
  const same = selectDeliveryOrder(draft, { ...orderSummary })
  assert.deepEqual(same.lines, draft.lines)
  const changed = selectDeliveryOrder(draft, otherOrder)
  assert.deepEqual(changed.lines, [])
  assert.equal(changed.order.id, otherOrderId)
  assert.equal(changed.receipt_number, draft.receipt_number)
  assert.equal(changed.received_date, draft.received_date)
  assert.equal(changed.notes, draft.notes)
  assert.deepEqual(selectDeliveryOrder(draft, null).lines, [])
  assert.equal(draft.lines.length, 1)
})

test('delivery line selection prevents duplicates and retains stable keys and entered quantities', () => {
  const draft = deliveryDraft()
  const unchanged = selectDeliveryLine(draft, orderLineId, true)
  assert.deepEqual(unchanged.lines, draft.lines)
  const expanded = selectDeliveryLine(unchanged, secondOrderLineId, true)
  assert.equal(expanded.lines.length, 2)
  assert.equal(expanded.lines[0].key, 'delivery-local')
  assert.equal(expanded.lines[0].quantity_received, '8.000')
  assert.notEqual(expanded.lines[1].key, expanded.lines[0].key)
  const removed = selectDeliveryLine(expanded, orderLineId, false)
  assert.deepEqual(removed.lines.map((line) => line.purchase_order_line_id), [secondOrderLineId])
})

test('changing invoice supplier clears order and mappings while retaining priced input and keys', () => {
  const draft = invoiceDraft()
  assert.deepEqual(selectInvoiceSupplier(draft, { ...supplier }).lines, draft.lines)
  const changed = selectInvoiceSupplier(draft, otherSupplier)
  assert.equal(changed.supplier.id, otherSupplierId)
  assert.equal(changed.order, null)
  assert.equal(changed.lines[0].purchase_order_line_id, null)
  for (const name of ['key', 'description', 'quantity', 'unit_price']) assert.equal(changed.lines[0][name], draft.lines[0][name])
  for (const name of ['invoice_number', 'invoice_date', 'due_date', 'tax_amount', 'notes']) assert.equal(changed[name], draft[name])
  assert.equal(draft.lines[0].purchase_order_line_id, orderLineId)
})

test('changing invoice order clears mappings, preserves same-order mappings, and rejects another supplier', () => {
  const draft = invoiceDraft()
  assert.deepEqual(selectInvoiceOrder(draft, { ...orderSummary }).lines, draft.lines)
  for (const selection of [otherOrder, null, { ...otherOrder, supplier_id: otherSupplierId }]) {
    const changed = selectInvoiceOrder(draft, selection)
    assert.equal(changed.lines[0].purchase_order_line_id, null)
    assert.equal(changed.lines[0].key, draft.lines[0].key)
    assert.equal(changed.lines[0].quantity, '10.000')
    assert.equal(changed.lines[0].unit_price, '25.0000')
    if (selection?.supplier_id === otherSupplierId) assert.equal(changed.order, null)
  }
})

test('selected-order detail rejects obsolete order and supplier responses', () => {
  assert.equal(selectedOrderDetail(orderSummary, order), order)
  assert.equal(selectedOrderDetail(orderSummary, order, supplierId), order)
  assert.equal(selectedOrderDetail(otherOrder, order), null)
  assert.equal(selectedOrderDetail(orderSummary, order, otherSupplierId), null)
  assert.equal(selectedOrderDetail(null, order), null)
  assert.equal(selectedOrderDetail(orderSummary, null), null)
})

test('order selection changes cancel old reads and cannot repopulate dependent mappings', async () => {
  const scope = createRequestScope()
  let draft = invoiceDraft()
  const oldController = scope.start()
  let finishOld
  const oldRead = new Promise((resolve) => { finishOld = resolve })
  let displayed = null
  const completion = oldRead.then((saved) => {
    if (scope.isCurrent(oldController)) displayed = selectedOrderDetail(draft.order, saved, draft.supplier.id)
  })
  draft = selectInvoiceOrder(draft, otherOrder)
  const currentController = scope.start()
  finishOld(order)
  await completion
  assert.equal(oldController.signal.aborted, true)
  assert.equal(displayed, null)
  assert.equal(draft.order.id, otherOrderId)
  assert.equal(draft.lines[0].purchase_order_line_id, null)
  assert.equal(scope.isCurrent(currentController), true)
})

test('delivery validation checks membership, duplicates and positive string quantities without overdelivery rules', () => {
  assert.deepEqual(validateDelivery(deliveryInput, order), [])
  assert.deepEqual(validateDelivery({ ...deliveryInput, lines: [{ purchase_order_line_id: orderLineId, quantity_received: '999999999.999' }] }, order), [])
  assert.equal(fields(validateDelivery({ ...deliveryInput, lines: [...deliveryInput.lines, ...deliveryInput.lines] }, order)).includes('lines[1].purchase_order_line_id'), true)
  assert.equal(fields(validateDelivery({ ...deliveryInput, lines: [{ purchase_order_line_id: secondOrderLineId, quantity_received: '8' }] }, { ...order, lines: [order.lines[0]] })).includes('lines[0].purchase_order_line_id'), true)
  assert.equal(fields(validateDelivery({ ...deliveryInput, purchase_order_id: otherOrderId }, order)).includes('purchase_order_id'), true)
})

test('invoice validation allows repeated manual mappings, unmapped lines, and no order', () => {
  assert.deepEqual(validateInvoice(invoiceInput, order), [])
  assert.deepEqual(validateInvoice({ ...invoiceInput, lines: [...invoiceInput.lines, ...invoiceInput.lines] }, order), [])
  assert.deepEqual(validateInvoice({ ...invoiceInput, lines: [{ ...invoiceInput.lines[0], purchase_order_line_id: null }] }, order), [])
  assert.deepEqual(validateInvoice({ ...invoiceInput, purchase_order_id: null, lines: [{ ...invoiceInput.lines[0], purchase_order_line_id: null }] }), [])
  assert.equal(fields(validateInvoice({ ...invoiceInput, purchase_order_id: null })).includes('lines[0].purchase_order_line_id'), true)
  assert.equal(fields(validateInvoice({ ...invoiceInput, supplier_id: otherSupplierId }, order)).includes('purchase_order_id'), true)
  assert.equal(fields(validateInvoice({ ...invoiceInput, lines: [{ ...invoiceInput.lines[0], purchase_order_line_id: secondOrderLineId }] }, { ...order, lines: [order.lines[0]] })).includes('lines[0].purchase_order_line_id'), true)
})

test('delivery and invoice decimal validation rejects numbers, notation, whitespace, scale and bounds', () => {
  for (const value of [8, '', '0', '-1', '+1', '1e1', 'NaN', 'Infinity', ' 1', '1 ', '1.0000', '1000000000']) {
    assert.equal(fields(validateDelivery({ ...deliveryInput, lines: [{ ...deliveryInput.lines[0], quantity_received: value }] }, order)).includes('lines[0].quantity_received'), true, `delivery ${JSON.stringify(value)}`)
    assert.equal(fields(validateInvoice({ ...invoiceInput, lines: [{ ...invoiceInput.lines[0], quantity: value }] }, order)).includes('lines[0].quantity'), true, `invoice ${JSON.stringify(value)}`)
  }
  for (const value of [25, '-1', '+1', '1e1', 'NaN', 'Infinity', ' 1', '1.00000', '10000000000']) assert.equal(fields(validateInvoice({ ...invoiceInput, lines: [{ ...invoiceInput.lines[0], unit_price: value }] }, order)).includes('lines[0].unit_price'), true)
  for (const value of [12.34, '', '-1', '+1', '1e1', 'NaN', 'Infinity', ' 1', '1 ', '0.001', '10000000000000000']) assert.equal(fields(validateInvoice({ ...invoiceInput, tax_amount: value }, order)).includes('tax_amount'), true)
  assert.deepEqual(validateInvoice({ ...invoiceInput, tax_amount: MONEY_MAX }, order), [])
})

test('new document validation follows calendar, text, EUR, and 1-100 line limits', () => {
  assert.equal(fields(validateDelivery({ ...deliveryInput, receipt_number: ' ', received_date: '2026-02-30', notes: 'x'.repeat(2001) }, order)).includes('receipt_number'), true)
  assert.equal(fields(validateDelivery({ ...deliveryInput, received_date: '2026-02-30' }, order)).includes('received_date'), true)
  assert.equal(fields(validateDelivery({ ...deliveryInput, notes: 'x'.repeat(2001) }, order)).includes('notes'), true)
  for (const length of [0, 101]) {
    assert.equal(fields(validateDelivery({ ...deliveryInput, lines: Array(length).fill(deliveryInput.lines[0]) })).includes('lines'), true)
    assert.equal(fields(validateInvoice({ ...invoiceInput, lines: Array(length).fill(invoiceInput.lines[0]) })).includes('lines'), true)
  }
  assert.deepEqual(validateInvoice({ ...invoiceInput, lines: Array(100).fill(invoiceInput.lines[0]) }, order), [])
  for (const input of [{ ...invoiceInput, invoice_number: ' ' }, { ...invoiceInput, invoice_number: 'x'.repeat(65) }]) assert.equal(fields(validateInvoice(input, order)).includes('invoice_number'), true)
  for (const date of ['2026-02-30', '2026-10-15T00:00:00Z']) assert.equal(fields(validateInvoice({ ...invoiceInput, invoice_date: date }, order)).includes('invoice_date'), true)
  assert.equal(fields(validateInvoice({ ...invoiceInput, due_date: '2026-10-14' }, order)).includes('due_date'), true)
  assert.equal(fields(validateInvoice({ ...invoiceInput, due_date: '2026-02-30' }, order)).includes('due_date'), true)
  assert.deepEqual(validateInvoice({ ...invoiceInput, due_date: '2026-10-15', tax_amount: '0' }, order), [])
  assert.deepEqual(validateInvoice({ ...invoiceInput, due_date: null }, order), [])
  assert.equal(fields(validateInvoice({ ...invoiceInput, currency: 'GBP' }, order)).includes('currency'), true)
})

test('delivery POST maps the website record to /delivery-receipts and strips copied server fields', async (t) => {
  const payload = { ...deliveryInput, id: 'untrusted', workspace_id: 'untrusted', lines: deliveryInput.lines.map((line) => ({ ...line, key: 'local', purchase_order_id: 'untrusted', line_no: 1 })) }
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.equal(path, '/api/delivery-receipts')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(options.body), deliveryInput)
    return Response.json(receipt, { status: 201 })
  })
  const saved = await createDeliveryReceipt(payload)
  assert.equal(saved.id, receiptId)
  assert.notEqual(saved.id, saved.lines[0].id)
  assert.equal(saved.lines[0].quantity_received, '8.000')
  assert.equal(payload.lines[0].key, 'local')
})

test('invoice POST retains nested strings and explicit tax while discarding client status/totals/internal IDs', async (t) => {
  const payload = { ...invoiceInput, status: 'approved', total: 'untrusted', subtotal: 'untrusted', lines: invoiceInput.lines.map((line) => ({ ...line, key: 'local', line_total: 'untrusted', purchase_order_id: 'untrusted' })) }
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.equal(path, '/api/invoices')
    assert.equal(options.method, 'POST')
    assert.deepEqual(JSON.parse(options.body), invoiceInput)
    return Response.json(invoice, { status: 201 })
  })
  const saved = await createInvoice(payload)
  assert.equal(saved.id, invoiceId)
  assert.notEqual(saved.id, saved.lines[0].id)
  assert.equal(saved.status, 'draft')
  assert.equal(saved.subtotal, '250.00')
  assert.equal(saved.tax_amount, '12.34')
  assert.equal(saved.total, '262.34')
})

test('invoice POST without an order preserves null relationships and server total', async (t) => {
  const input = { ...invoiceInput, purchase_order_id: null, due_date: null, tax_amount: '0.00', lines: [{ ...invoiceInput.lines[0], purchase_order_line_id: null }] }
  const saved = { ...invoice, purchase_order_id: null, due_date: null, tax_amount: '0.00', total: '250.00', lines: [{ ...invoice.lines[0], purchase_order_line_id: null }] }
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.deepEqual(JSON.parse(options.body), input)
    return Response.json(saved, { status: 201 })
  })
  assert.deepEqual(await createInvoice(input), saved)
})

test('paginated delivery and invoice reads retain filters, totals and header-only shapes', async (t) => {
  const seen = []
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    seen.push(path)
    assert.equal(options.method, 'GET')
    assert.equal(options.cache, 'no-store')
    return Response.json(path.includes('/delivery-receipts') ? page([receiptSummary], 20, 40, 67) : page([invoiceSummary], 20, 40, 67))
  })
  const deliveries = await getDeliveryReceipts({ limit: 20, offset: 40, purchase_order_id: orderId })
  const invoices = await getInvoices({ limit: 20, offset: 40, supplier_id: supplierId, purchase_order_id: orderId })
  assert.equal(deliveries.total, 67)
  assert.equal(deliveries.items[0].receipt_number, 'DR-SYNTHETIC-11')
  assert.equal(invoices.total, 67)
  assert.equal(invoices.items[0].total, '262.34')
  assert.equal('lines' in deliveries.items[0], false)
  assert.equal('lines' in invoices.items[0], false)
  assert.deepEqual(seen, [`/api/delivery-receipts?limit=20&offset=40&purchase_order_id=${orderId}`, `/api/invoices?limit=20&offset=40&supplier_id=${supplierId}&purchase_order_id=${orderId}`])
})

test('delivery and invoice detail reads preserve ordered nested records', async (t) => {
  const seen = []
  t.mock.method(globalThis, 'fetch', async (path) => { seen.push(path); return Response.json(path.includes('/delivery-receipts') ? receipt : invoice) })
  assert.deepEqual(await getDeliveryReceipt(receiptId), receipt)
  assert.deepEqual(await getInvoice(invoiceId), invoice)
  assert.deepEqual(seen, [`/api/delivery-receipts/${receiptId}`, `/api/invoices/${invoiceId}`])
})

test('malformed new list filters or page bounds never dispatch requests', (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(page([])) })
  for (const request of [
    () => getDeliveryReceipts({ limit: 0, offset: 0 }),
    () => getDeliveryReceipts({ limit: 20, offset: 0, purchase_order_id: 'bad' }),
    () => getInvoices({ limit: 101, offset: 0 }),
    () => getInvoices({ limit: 20, offset: 10001 }),
    () => getInvoices({ limit: 20, offset: 0, supplier_id: 'bad' }),
    () => getInvoices({ limit: 20, offset: 0, purchase_order_id: 'bad' }),
  ]) assert.throws(request, (error) => error.kind === 'validation')
  assert.equal(calls, 0)
})

test('invalid delivery or invoice input is rejected before POST dispatch', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(invoice, { status: 201 }) })
  await assert.rejects(createDeliveryReceipt({ ...deliveryInput, lines: [{ ...deliveryInput.lines[0], quantity_received: 8 }] }), (error) => error.kind === 'validation' && !error.uncertainWrite)
  await assert.rejects(createInvoice({ ...invoiceInput, tax_amount: 12.34 }), (error) => error.kind === 'validation' && !error.uncertainWrite)
  await assert.rejects(createInvoice({ ...invoiceInput, purchase_order_id: null }), (error) => error.kind === 'validation' && !error.uncertainWrite)
  assert.equal(calls, 0)
})

for (const [status, code, kind] of [[422, 'validation_error', 'validation'], [404, 'not_found', 'missing'], [409, 'conflict', 'conflict'], [503, 'service_unavailable', 'unavailable'], [500, 'internal_error', 'server']]) {
  test(`delivery/invoice HTTP ${status} retains the business error envelope and known rollback result`, async (t) => {
    const details = [{ field: 'lines[0].purchase_order_line_id', message: 'Choose a line from the selected order.' }]
    t.mock.method(globalThis, 'fetch', async () => Response.json(envelope(code, details), { status }))
    for (const request of [() => createDeliveryReceipt(deliveryInput), () => createInvoice(invoiceInput)]) {
      await assert.rejects(request(), (error) => {
        assert.equal(error.kind, kind)
        assert.equal(error.status, status)
        assert.deepEqual(error.details, details)
        assert.equal(error.uncertainWrite, false)
        return true
      })
    }
  })
}

test('unexpected gateway errors stay generic and leave dispatched invoice saves uncertain', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>private database failure</html>', { status: 502 }))
  await assert.rejects(createInvoice(invoiceInput), (error) => error.kind === 'server' && error.uncertainWrite && !error.message.includes('private'))
})

test('malformed decimal outputs, status and nested parents fail response validation', async (t) => {
  for (const bad of [
    { ...receipt, lines: [{ ...receipt.lines[0], quantity_received: 8 }] },
    { ...receipt, lines: [{ ...receipt.lines[0], quantity_received: '8' }] },
    { ...receipt, lines: [{ ...receipt.lines[0], delivery_receipt_id: invoiceId }] },
  ]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(bad))
    await assert.rejects(getDeliveryReceipt(receiptId), (error) => error.kind === 'invalid-response' && !error.uncertainWrite)
  }
  for (const bad of [
    { ...invoice, tax_amount: 12.34 },
    { ...invoice, total: '262.3' },
    { ...invoice, status: 'approved' },
    { ...invoice, lines: [{ ...invoice.lines[0], invoice_id: receiptId }] },
    { ...invoice, lines: [{ ...invoice.lines[0], quantity: '10' }] },
  ]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(bad, { status: 201 }))
    await assert.rejects(createInvoice(invoiceInput), (error) => error.kind === 'invalid-response' && error.uncertainWrite)
  }
})

test('dispatched delivery and invoice network failures retain input and never automatically retry', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; throw new TypeError('private-network-detail') })
  const delivery = structuredClone(deliveryInput)
  const bill = structuredClone(invoiceInput)
  await assert.rejects(createDeliveryReceipt(delivery), (error) => error.kind === 'network' && error.uncertainWrite && !error.message.includes('private'))
  await assert.rejects(createInvoice(bill), (error) => error.kind === 'network' && error.uncertainWrite)
  assert.equal(calls, 2)
  assert.deepEqual(delivery, deliveryInput)
  assert.deepEqual(bill, invoiceInput)
})

test('delivery header timeout is bounded and does not mark a read as an uncertain write', { timeout: 1000 }, async (t) => {
  t.mock.method(globalThis, 'fetch', (path, { signal }) => waitForAbort(signal))
  await assert.rejects(getDeliveryReceipts(undefined, { timeoutMs: 15 }), (error) => error.kind === 'timeout' && !error.uncertainWrite)
})

test('invoice response-body timeout remains bounded when the body ignores cancellation', { timeout: 1000 }, async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return { ok: true, status: 201, json: () => new Promise(() => {}) } })
  const draft = structuredClone(invoiceInput)
  await assert.rejects(createInvoice(draft, { timeoutMs: 15 }), (error) => error.kind === 'timeout' && error.uncertainWrite)
  assert.equal(calls, 1)
  assert.deepEqual(draft, invoiceInput)
})

test('obsolete delivery detail read is cancelled while reading its response body', async (t) => {
  const controller = new AbortController()
  let startBody
  const bodyStarted = new Promise((resolve) => { startBody = resolve })
  t.mock.method(globalThis, 'fetch', async (path, { signal }) => ({ ok: true, status: 200, json: () => { startBody(); return waitForAbort(signal) } }))
  const pending = getDeliveryReceipt(receiptId, { signal: controller.signal })
  await bodyStarted
  controller.abort()
  await assert.rejects(pending, (error) => error.kind === 'cancelled' && !error.uncertainWrite)
})

test('leaving an invoice save interrupts its body read and reports a potentially saved document', async (t) => {
  const controller = new AbortController()
  let startBody
  const bodyStarted = new Promise((resolve) => { startBody = resolve })
  t.mock.method(globalThis, 'fetch', async (path, { signal }) => ({ ok: true, status: 201, json: () => { startBody(); return waitForAbort(signal) } }))
  const pending = createInvoice(invoiceInput, { signal: controller.signal })
  await bodyStarted
  controller.abort()
  await assert.rejects(pending, (error) => error.kind === 'cancelled' && error.uncertainWrite)
})

test('already-cancelled new saves do not dispatch or claim a possible saved record', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(invoice, { status: 201 }) })
  const controller = new AbortController()
  controller.abort()
  for (const request of [() => createDeliveryReceipt(deliveryInput, { signal: controller.signal }), () => createInvoice(invoiceInput, { signal: controller.signal })]) await assert.rejects(request(), (error) => error.kind === 'cancelled' && !error.uncertainWrite)
  assert.equal(calls, 0)
})

test('new list reads recover only after an explicit later request', async (t) => {
  let available = false
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; if (!available) throw new TypeError('offline'); return Response.json(page([invoiceSummary])) })
  await assert.rejects(getInvoices(), (error) => error.kind === 'network' && !error.uncertainWrite)
  assert.equal(calls, 1)
  available = true
  assert.equal((await getInvoices()).items[0].id, invoiceId)
  assert.equal(calls, 2)
})
