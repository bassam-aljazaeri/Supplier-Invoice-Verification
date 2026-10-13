import type { ErrorDetail, LineDraft } from '../types.ts'
import { fieldError, newLine } from '../validation.ts'
import { TextField } from './FormFeedback.tsx'

export default function LineItemsForm({ lines, onChange, details }: { lines: LineDraft[]; onChange: (lines: LineDraft[]) => void; details: ErrorDetail[] }) {
  const update = (index: number, field: 'description' | 'quantity' | 'unit_price', value: string) => onChange(lines.map((line, position) => position === index ? { ...line, [field]: value } : line))
  const error = fieldError(details, 'lines')
  return <fieldset className="line-items" tabIndex={-1} data-field="lines" aria-describedby={error ? 'lines-error' : 'lines-hint'}>
    <legend>Order lines</legend>
    <p className="hint" id="lines-hint">Add 1–100 lines. Totals are calculated when the order is saved.</p>
    {error && <p className="field-error" id="lines-error">{error}</p>}
    {lines.map((line, index) => <fieldset className="line-card" key={line.key} tabIndex={-1} data-field={`lines[${index}]`} aria-invalid={!!fieldError(details, `lines[${index}]`)} aria-describedby={fieldError(details, `lines[${index}]`) ? `line-${line.key}-error` : undefined}>
      <legend>Line {index + 1}</legend>
      {fieldError(details, `lines[${index}]`) && <p className="field-error" id={`line-${line.key}-error`}>{fieldError(details, `lines[${index}]`)}</p>}
      <TextField id={`line-${line.key}-description`} field={`lines[${index}].description`} label="Description" value={line.description} details={details} hint="Required; up to 500 characters." onChange={(value) => update(index, 'description', value)} />
      <div className="field-grid">
        <TextField id={`line-${line.key}-quantity`} field={`lines[${index}].quantity`} label="Quantity" value={line.quantity} details={details} decimal hint="Positive; up to 3 decimal places. Maximum 999999999.999." onChange={(value) => update(index, 'quantity', value)} />
        <TextField id={`line-${line.key}-price`} field={`lines[${index}].unit_price`} label="Unit price (EUR)" value={line.unit_price} details={details} decimal hint="Zero or greater; up to 4 decimal places. Maximum 9999999999.9999." onChange={(value) => update(index, 'unit_price', value)} />
      </div>
      <button type="button" disabled={lines.length <= 1} aria-label={`Remove line ${index + 1}`} onClick={() => onChange(lines.filter((item) => item.key !== line.key))}>Remove line</button>
    </fieldset>)}
    <div className="actions"><button type="button" disabled={lines.length >= 100} onClick={() => onChange([...lines, newLine()])}>Add line</button><span role="status">{lines.length} of 100 lines</span></div>
  </fieldset>
}
