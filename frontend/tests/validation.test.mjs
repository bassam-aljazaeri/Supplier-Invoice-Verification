import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fieldError, focusError, newLine, newOrderDraft, orderPayload, supplierPayload, validDate, validDecimal, validateOrder, validateSupplier, QUANTITY_MAX, PRICE_MAX } from '../src/validation.ts'

const id = '10000000-0000-4000-8000-000000000001'
const order = (overrides = {}) => ({ supplier_id: id, po_number: 'PO-FICTIONAL', order_date: '2026-10-13', currency: 'EUR', notes: null, lines: [{ description: 'Keyboard', quantity: '10.000', unit_price: '25.0000' }], ...overrides })
test('payloads trim accepted text and retain decimal strings without local totals or keys', () => {
  const draft = { supplier: { id, name: 'Fictional' }, po_number: ' PO-FICTIONAL ', order_date: '2026-10-13', notes: ' ', lines: [{ key: 'temporary', description: ' Keyboard ', quantity: '10.000', unit_price: '25.0000', line_total: 'bad' }] }
  assert.deepEqual(orderPayload(draft), order())
  assert.equal(draft.lines[0].description, ' Keyboard ')
  assert.deepEqual(supplierPayload({ supplier_code: ' SYNTHETIC ', name: ' Fictional ', notes: ' ' }), { supplier_code: 'SYNTHETIC', name: 'Fictional', notes: null })
})
for (const value of [10, 10.0, true, null, '', ' 10', '10 ', '+10', '-10', '1e1', 'NaN', 'Infinity', '1,000', '.1', '1.', '١٠', '0', '0.000', '1.0000', '1000000000', '0'.repeat(33)]) {
  test(`rejects invalid quantity ${JSON.stringify(value)} without numeric coercion`, () => assert.equal(validDecimal(value, 3, QUANTITY_MAX, true), false))
}
for (const value of [25, '-1', '+1', '1e1', 'NaN', 'Infinity', '1.00000', '10000000000', ' 1']) {
  test(`rejects invalid unit price ${JSON.stringify(value)}`, () => assert.equal(validDecimal(value, 4, PRICE_MAX, false), false))
}
test('decimal boundaries and leading-zero comparison are exact', () => {
  for (const value of ['0.001', '10', QUANTITY_MAX, '00010.000']) assert.equal(validDecimal(value, 3, QUANTITY_MAX, true), true)
  for (const value of ['0', '0.0000', '25', PRICE_MAX]) assert.equal(validDecimal(value, 4, PRICE_MAX, false), true)
  assert.equal(validDecimal('9999999999.99990', 4, PRICE_MAX, false), false)
  assert.equal(validDecimal('0001000000000', 3, QUANTITY_MAX, true), false)
  assert.equal(validateOrder(order()).length, 0)
})
test('date validation uses calendar dates without timezone conversions', () => {
  for (const value of ['0001-01-01', '9999-12-31', '2024-02-29', '2000-02-29']) assert.equal(validDate(value), true)
  for (const value of ['0000-01-01', '2026-02-29', '1900-02-29', '2026-04-31', '2026-10-13T00:00:00Z', '2026-1-1', ' 2026-10-13', 20261013]) assert.equal(validDate(value), false)
})
test('supplier validation matches trimmed text and optional note bounds', () => {
  assert.equal(validateSupplier({ supplier_code: ' S ', name: ' N ', notes: ' ' }).length, 0)
  assert.equal(validateSupplier({ supplier_code: 'X'.repeat(64), name: '🙂'.repeat(200), notes: 'X'.repeat(2000) }).length, 0)
  assert.deepEqual(validateSupplier({ supplier_code: ' ', name: 'X'.repeat(201), notes: 'X'.repeat(2001) }).map((error) => error.field), ['supplier_code', 'name', 'notes'])
})
test('order validation exposes indexed field errors and document limits', () => {
  const errors = validateOrder(order({ supplier_id: '', po_number: ' ', order_date: '2026-02-30', lines: [{ description: ' ', quantity: '0', unit_price: '-1' }] }))
  assert.deepEqual(errors.map((error) => error.field), ['supplier_id', 'po_number', 'order_date', 'lines[0].description', 'lines[0].quantity', 'lines[0].unit_price'])
  assert.equal(fieldError(errors, 'lines[0].quantity').includes('positive'), true)
  assert.equal(validateOrder(order({ lines: [] }))[0].field, 'lines')
  assert.equal(validateOrder(order({ lines: Array(101).fill(order().lines[0]) }))[0].field, 'lines')
  assert.equal(validateOrder(order({ lines: Array(100).fill(order().lines[0]) })).length, 0)
  assert.equal(validateOrder(order({ currency: 'USD' }))[0].field, 'currency')
})
test('new unsaved lines have stable distinct keys and no record IDs', () => {
  const draft = newOrderDraft()
  const second = newLine()
  const edited = { ...draft.lines[0], quantity: '10' }
  assert.equal(edited.key, draft.lines[0].key)
  assert.notEqual(second.key, edited.key)
  assert.equal('id' in edited, false)
  assert.equal(draft.supplier, null)
})
test('focus helper chooses the first invalid control in document order or the summary', () => {
  const focused = []
  const fields = ['po_number', 'lines[0].quantity'].map((field) => ({ dataset: { field }, focus: () => focused.push(field) }))
  const form = { querySelectorAll: () => fields, querySelector: () => ({ focus: () => focused.push('summary') }) }
  focusError(form, [{ field: 'lines[0].quantity', message: 'Invalid' }, { field: 'po_number', message: 'Invalid' }])
  focusError(form, [])
  assert.deepEqual(focused, ['po_number', 'summary'])
})
