import { ApiFailure, privateContextVersion, privateRequest } from './api.ts'
import type { RequestOptions } from './api.ts'
import type { PageParams, RecordPage } from './types.ts'
import { DEFAULT_PAGE, validPage } from './navigation.ts'
import { isUuid } from './validation.ts'
import { documentErrors, documentStates } from './documentTypes.ts'
import type { DocumentRecord } from './documentTypes.ts'

export const MAX_DOCUMENT_BYTES = 5000000
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const date = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value))
export function isDocument(value: unknown): value is DocumentRecord {
  return object(value) && isUuid(value.id) && isUuid(value.workspace_id) && isUuid(value.uploader_id)
    && typeof value.original_filename === 'string' && value.original_filename.length > 0
    && Number.isSafeInteger(value.byte_size) && (value.byte_size as number) >= 1 && (value.byte_size as number) <= MAX_DOCUMENT_BYTES
    && (value.detected_type === null || ['pdf', 'jpeg', 'png'].includes(value.detected_type as string))
    && documentStates.includes(value.state as DocumentRecord['state']) && typeof value.can_retry === 'boolean'
    && (value.error_code === null || documentErrors.includes(value.error_code as NonNullable<DocumentRecord['error_code']>))
    && (value.state !== 'accepted' || value.detected_type !== null)
    && (['rejected', 'failed'].includes(value.state as string) ? value.error_code !== null : value.error_code === null)
    && date(value.created_at) && date(value.updated_at) && (value.uploaded_at === null || date(value.uploaded_at)) && (value.finished_at === null || date(value.finished_at))
}
const isPage = (value: unknown): value is RecordPage<DocumentRecord> => object(value) && validPage({ limit: value.limit as number, offset: value.offset as number })
  && Number.isSafeInteger(value.total) && (value.total as number) >= 0 && Array.isArray(value.items) && value.items.length <= (value.limit as number) && value.items.every(isDocument)
const assertId = (id: string) => { if (!isUuid(id)) throw new ApiFailure('validation', 'Choose an available document.') }

export function validateDocumentFile(file: File | null) {
  if (!file) return 'Choose one file.'
  if (file.size < 1 || file.size > MAX_DOCUMENT_BYTES) return 'Choose a file of 1 to 5,000,000 bytes.'
  if (!/\.(pdf|jpe?g|png)$/i.test(file.name) || (file.type && !['application/pdf', 'image/jpeg', 'image/png', 'application/octet-stream'].includes(file.type))) return 'Choose a PDF, JPEG or PNG file.'
  return null
}
export function getDocuments(page: PageParams = DEFAULT_PAGE, options: RequestOptions = {}, attemptKey?: string) {
  if (!validPage(page)) throw new ApiFailure('validation', 'Invalid page limits.')
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) })
  if (attemptKey !== undefined) { assertId(attemptKey); query.set('upload_attempt_key', attemptKey) }
  return privateRequest(`/documents?${query}`, isPage, options)
}
export function getDocument(id: string, options: RequestOptions = {}) {
  assertId(id)
  return privateRequest(`/documents/${id}`, (value): value is DocumentRecord => isDocument(value) && value.id === id, options)
}
export function uploadDocument(file: File, attemptKey: string, options: RequestOptions = {}) {
  assertId(attemptKey)
  const error = validateDocumentFile(file)
  if (error) throw new ApiFailure('validation', error, [{ field: 'file', message: error }])
  const form = new FormData()
  form.append('file', file)
  return privateRequest('/documents', isDocument, { ...options, timeoutMs: options.timeoutMs ?? 90000 }, undefined, 'business', 'POST', { form, idempotencyKey: attemptKey, statuses: [200, 202], uncertainServerError: true })
}
export function retryDocument(id: string, options: RequestOptions = {}) {
  assertId(id)
  return privateRequest(`/documents/${id}/retry`, (value): value is DocumentRecord => isDocument(value) && value.id === id, options, undefined, 'business', 'POST', { statuses: [202], uncertainServerError: true })
}

type LocalGrant = { document_id: string; workspace_id: string; delivery: 'local_authenticated'; url: string; expires_at: string }
export function localDownloadPath(url: string, id: string) {
  const prefix = `/api/documents/${id}/local-content?`
  if (!url.startsWith(prefix) || /[\\\r\n#]/.test(url)) throw new ApiFailure('invalid-response', 'The download could not be prepared.')
  const query = new URLSearchParams(url.slice(prefix.length))
  if (query.size !== 1 || query.getAll('ticket').length !== 1 || !query.get('ticket') || query.get('ticket')!.length > 512) throw new ApiFailure('invalid-response', 'The download could not be prepared.')
  return url.slice(4)
}
export async function downloadDocument(record: DocumentRecord, options: RequestOptions = {}) {
  if (record.state !== 'accepted') throw new ApiFailure('conflict', 'Only accepted documents can be downloaded.')
  assertId(record.id)
  const version = privateContextVersion()
  const grant = await privateRequest(`/documents/${record.id}/download-url`, (value): value is LocalGrant => object(value)
    && value.document_id === record.id && value.workspace_id === record.workspace_id && value.delivery === 'local_authenticated'
    && typeof value.url === 'string' && date(value.expires_at), options, undefined, 'business', 'POST', { statuses: [200], readOnly: true })
  if (version !== privateContextVersion()) throw new ApiFailure('cancelled', 'The request was interrupted.')
  // This milestone accepts only the local authenticated contract. External targets
  // are rejected before fetching; app credentials can never follow a storage URL.
  const path = localDownloadPath(grant.url, record.id)
  const mime = { pdf: 'application/pdf', jpeg: 'image/jpeg', png: 'image/png' }[record.detected_type!]
  const blob = await privateRequest(path, (value): value is Blob => value instanceof Blob && value.size === record.byte_size && value.type === mime, options, undefined, 'business', 'GET', { blob: { maximum: MAX_DOCUMENT_BYTES } })
  if (version !== privateContextVersion()) throw new ApiFailure('cancelled', 'The request was interrupted.')
  return { blob, filename: `document-${record.id}.${record.detected_type === 'jpeg' ? 'jpg' : record.detected_type}` }
}
