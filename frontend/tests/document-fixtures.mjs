import { workspaceId, userId, timestamp } from './auth-fixtures.mjs'

export const documentId = '80000000-0000-4000-8000-000000000011'
export const attemptKey = '90000000-0000-4000-8000-000000000011'
export const fictionalFile = () => new File(['%PDF-1.7\nFictional invoice fixture only.'], 'fictional-invoice.pdf', { type: 'application/pdf' })
export function documentRecord(overrides = {}) {
  return { id: documentId, workspace_id: workspaceId, uploader_id: userId,
    original_filename: 'fictional-invoice.pdf', byte_size: fictionalFile().size, detected_type: null,
    state: 'queued', error_code: null, can_retry: false, created_at: timestamp, updated_at: timestamp,
    uploaded_at: timestamp, finished_at: null, ...overrides }
}
export const grant = (overrides = {}) => ({ document_id: documentId, workspace_id: workspaceId, delivery: 'local_authenticated',
  url: `/api/documents/${documentId}/local-content?ticket=FICTIONAL-TICKET`, expires_at: '2026-11-14T12:00:00Z', ...overrides })
