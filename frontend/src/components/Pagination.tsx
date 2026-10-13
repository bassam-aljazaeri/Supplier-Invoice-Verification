import type { PageParams } from '../types.ts'
import { MAX_OFFSET, pagination } from '../navigation.ts'

export default function Pagination({ page, total, count, onPage }: { page: PageParams; total: number; count: number; onPage: (offset: number) => void }) {
  const state = pagination(page, total, count)
  return <div className="pagination" aria-label="Pagination">
    <p role="status">{state.label}</p>
    <div className="actions">
      <button type="button" disabled={!state.hasPrevious} onClick={() => onPage(state.previous)}>Previous</button>
      <button type="button" disabled={!state.hasNext} onClick={() => onPage(state.next)}>Next</button>
    </div>
    {page.offset + page.limit > MAX_OFFSET && page.offset + count < total && <p className="hint">Further results exceed the available page range.</p>}
  </div>
}
