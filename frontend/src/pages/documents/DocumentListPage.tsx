import { useCallback } from 'react'
import { getDocuments } from '../../documentApi.ts'
import { documentStatus } from '../../documentTypes.ts'
import type { DocumentRecord } from '../../documentTypes.ts'
import type { PageParams } from '../../types.ts'
import { useCanCreate } from '../../authContext.tsx'
import { useRead } from '../../hooks/useBusiness.ts'
import { listHash, navigate } from '../../navigation.ts'
import Pagination from '../../components/Pagination.tsx'
import RequestState from '../../components/RequestState.tsx'

export function DocumentTable({ documents }: { documents: DocumentRecord[] }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label="Documents"><table>
    <caption className="sr-only">Documents, newest first</caption>
    <thead><tr><th scope="col">Filename</th><th scope="col">Status</th><th scope="col">Type</th><th scope="col">Bytes</th><th scope="col">Uploaded (UTC)</th></tr></thead>
    <tbody>{documents.map((record) => <tr key={record.id}>
      <td className="document-filename"><a href={`#/documents/${record.id}`}>{record.original_filename}</a></td>
      <td><strong className="document-state">{record.state}</strong><p className="hint">{documentStatus[record.state]}</p></td>
      <td>{record.detected_type?.toUpperCase() ?? 'Not validated'}</td><td>{record.byte_size.toLocaleString('en-US')}</td>
      <td>{record.uploaded_at ?? 'Not finalized'}</td>
    </tr>)}</tbody>
  </table></div>
}

export default function DocumentListPage({ page }: { page: PageParams }) {
  const canUpload = useCanCreate()
  const { limit, offset } = page
  const load = useCallback((signal: AbortSignal) => getDocuments({ limit, offset }, { signal }), [limit, offset])
  const result = useRead(`documents-${limit}-${offset}`, load)
  return <section className="business-panel" aria-busy={result.loading}>
    <div className="panel-heading"><h2>Documents</h2>{canUpload && <a className="button-link" href="#/documents/new">Upload document</a>}</div>
    <p>Private fictional invoice files in this workspace. Accepted means the file passed validation; it does not mean an invoice was matched or approved.</p>
    <p>Newest documents appear first. New uploads can shift later pages. <a href="#/documents?limit=20&offset=0">Open the first page</a>.</p>
    <RequestState loading={result.loading} error={result.error} retry={result.retry} />
    {!result.loading && !result.error && <button type="button" onClick={result.retry}>Refresh documents</button>}
    {result.data && <>
      {result.data.items.length ? <DocumentTable documents={result.data.items} /> : <p role="status">No documents on this page.</p>}
      <Pagination page={page} total={result.data.total} count={result.data.items.length} onPage={(next) => navigate(listHash('documents', { ...page, offset: next }))} />
    </>}
  </section>
}
