export const documentStates = ['receiving', 'queued', 'processing', 'accepted', 'rejected', 'failed'] as const
export type DocumentState = typeof documentStates[number]
export type DocumentType = 'pdf' | 'jpeg' | 'png'
export const documentErrors = ['invalid_file', 'unsupported_type', 'pdf_encrypted', 'pdf_page_count', 'image_frame_count', 'image_dimensions', 'parser_limit', 'storage_unavailable', 'processing_interrupted', 'processing_error', 'upload_incomplete', 'storage_integrity'] as const
export type DocumentError = typeof documentErrors[number]
export type DocumentRecord = {
  id: string; workspace_id: string; uploader_id: string; original_filename: string
  byte_size: number; detected_type: DocumentType | null; state: DocumentState
  error_code: DocumentError | null; can_retry: boolean; created_at: string; updated_at: string
  uploaded_at: string | null; finished_at: string | null
}
export const activeDocument = (record: DocumentRecord) => ['receiving', 'queued', 'processing'].includes(record.state)
export const documentStatus: Record<DocumentState, string> = {
  receiving: 'Upload is being finalized.', queued: 'Waiting for file checks; service recovery may delay this.',
  processing: 'Checking file format and limits.', accepted: 'File checks passed; extraction has not started.',
  rejected: 'This file does not meet the supported format or limits. Upload a corrected file.', failed: 'File processing could not finish.',
}
export const documentErrorMessage: Record<DocumentError, string> = {
  invalid_file: 'The file could not be decoded. Choose a valid file.', unsupported_type: 'Only PDF, JPEG and PNG files are supported.',
  pdf_encrypted: 'Password-protected PDFs are not supported.', pdf_page_count: 'The PDF must contain exactly one page.',
  image_frame_count: 'Choose a single-frame image. Animated PNG and multi-image JPEG are not supported.',
  image_dimensions: 'Images must have at most 10,000,000 pixels and at most 10,000 pixels per dimension.',
  parser_limit: 'The file could not be validated within the processing limits. Choose a simpler file.',
  storage_unavailable: 'Private file storage was unavailable.', processing_interrupted: 'Processing was interrupted.',
  processing_error: 'Processing could not complete after temporary service errors.',
  upload_incomplete: 'The upload did not finish. Inspect the document list before starting another upload.',
  storage_integrity: 'Stored bytes could not be verified. This document cannot be retried.',
}
