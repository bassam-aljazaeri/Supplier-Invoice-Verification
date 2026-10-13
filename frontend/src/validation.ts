import type { ErrorDetail, OrderDraft, PurchaseOrderCreate, SupplierCreate, SupplierDraft } from './types.ts'

export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export const QUANTITY_MAX = '999999999.999'
export const PRICE_MAX = '9999999999.9999'
export const MONEY_MAX = '9999999999999999.99'

export function isUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_PATTERN.test(value)
}

// Compare decimal digits directly: no conversion to binary floating point.
export function validDecimal(value: unknown, scale: number, maximum: string, positive: boolean): value is string {
  if (typeof value !== 'string' || value.length < 1 || value.length > 32 || !new RegExp(`^[0-9]+(?:\\.[0-9]{1,${scale}})?$`).test(value)) return false
  const [whole, fraction = ''] = value.split('.')
  const normalized = whole.replace(/^0+/, '') || '0'
  const [maxWhole, maxFraction = ''] = maximum.split('.')
  if (normalized.length > maxWhole.length || (normalized.length === maxWhole.length && normalized > maxWhole)) return false
  if (normalized === maxWhole && fraction.padEnd(scale, '0') > maxFraction.padEnd(scale, '0')) return false
  return !positive || /[1-9]/.test(value)
}

export function validDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return year >= 1 && year <= 9999 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1]
}

function requiredText(errors: ErrorDetail[], field: string, value: unknown, maximum: number) {
  if (typeof value !== 'string' || !value.trim() || Array.from(value.trim()).length > maximum) {
    errors.push({ field, message: `Enter nonblank text of at most ${maximum} characters.` })
  }
}

function validateNotes(errors: ErrorDetail[], notes: unknown) {
  if (notes !== undefined && notes !== null && (typeof notes !== 'string' || Array.from(notes.trim()).length > 2000)) {
    errors.push({ field: 'notes', message: 'Notes must contain at most 2000 characters.' })
  }
}

export function validateSupplier(input: SupplierCreate): ErrorDetail[] {
  const errors: ErrorDetail[] = []
  requiredText(errors, 'supplier_code', input.supplier_code, 64)
  requiredText(errors, 'name', input.name, 200)
  validateNotes(errors, input.notes)
  return errors
}

export function validateOrder(input: PurchaseOrderCreate): ErrorDetail[] {
  const errors: ErrorDetail[] = []
  if (!isUuid(input.supplier_id)) errors.push({ field: 'supplier_id', message: 'Choose an available supplier.' })
  requiredText(errors, 'po_number', input.po_number, 64)
  if (!validDate(input.order_date)) errors.push({ field: 'order_date', message: 'Enter a valid calendar date (YYYY-MM-DD).' })
  if (input.currency !== 'EUR') errors.push({ field: 'currency', message: 'Use EUR.' })
  validateNotes(errors, input.notes)
  if (!Array.isArray(input.lines) || input.lines.length < 1 || input.lines.length > 100) {
    errors.push({ field: 'lines', message: 'Provide between 1 and 100 line items.' })
    return errors
  }
  input.lines.forEach((line, index) => {
    requiredText(errors, `lines[${index}].description`, line.description, 500)
    if (!validDecimal(line.quantity, 3, QUANTITY_MAX, true)) errors.push({ field: `lines[${index}].quantity`, message: `Enter a positive decimal string, up to ${QUANTITY_MAX}, with at most 3 fractional digits.` })
    if (!validDecimal(line.unit_price, 4, PRICE_MAX, false)) errors.push({ field: `lines[${index}].unit_price`, message: `Enter a nonnegative decimal string, up to ${PRICE_MAX}, with at most 4 fractional digits.` })
  })
  return errors
}

export function supplierPayload(draft: SupplierDraft): SupplierCreate {
  return { supplier_code: draft.supplier_code.trim(), name: draft.name.trim(), notes: draft.notes.trim() || null }
}

export function orderPayload(draft: OrderDraft): PurchaseOrderCreate {
  return {
    supplier_id: draft.supplier?.id ?? '', po_number: draft.po_number.trim(),
    order_date: draft.order_date, currency: 'EUR', notes: draft.notes.trim() || null,
    lines: draft.lines.map(({ description, quantity, unit_price }) => ({ description: description.trim(), quantity, unit_price })),
  }
}

export function newSupplierDraft(): SupplierDraft {
  return { supplier_code: '', name: '', notes: '' }
}

export function newLine() {
  return { key: crypto.randomUUID(), description: '', quantity: '', unit_price: '' }
}

export function newOrderDraft(): OrderDraft {
  return { supplier: null, po_number: '', order_date: '', notes: '', lines: [newLine()] }
}

export function fieldError(details: ErrorDetail[], field: string) {
  return details.filter((detail) => detail.field === field).map((detail) => detail.message).join(' ')
}

export function focusError(form: HTMLFormElement, details: ErrorDetail[]) {
  const control = Array.from(form.querySelectorAll<HTMLElement>('[data-field]')).find((element) => details.some((detail) => detail.field === element.dataset.field))
  ;(control ?? form.querySelector<HTMLElement>('.error-summary'))?.focus()
}
