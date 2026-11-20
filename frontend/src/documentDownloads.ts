import { ApiFailure } from './api.ts'

let expectedOrigin: string | null = null
const invalidGrant = () => new ApiFailure('invalid-response', 'The download could not be prepared.')

export function s3DownloadOrigin(value: unknown): string | null {
  // Match the server's supported standard regional virtual-host HTTPS origin.
  if (typeof value !== 'string' || !/^https:\/\/[a-z0-9][a-z0-9-]{1,61}[a-z0-9]\.s3\.(?:af|ap|ca|eu|il|me|mx|sa|us)-[a-z]+-\d\.amazonaws\.com$/.test(value)) return null
  return value
}

export function configureDocumentDownloads(origin: unknown) {
  expectedOrigin = s3DownloadOrigin(origin)
}

export function externalDownloadUrl(value: string) {
  try {
    if (!expectedOrigin || !value.startsWith(expectedOrigin + '/') || /[\\\r\n]/.test(value)) throw invalidGrant()
    const url = new URL(value)
    if (url.origin !== expectedOrigin || url.protocol !== 'https:' || url.username || url.password || url.port || url.hash || !url.search || url.pathname === '/') throw invalidGrant()
    return value
  } catch { throw invalidGrant() }
}

export function openExternalDownload(url: string) {
  // Browser navigation only. Never use fetch/privateRequest for a storage URL.
  const safeUrl = externalDownloadUrl(url)
  const link = document.createElement('a')
  link.href = safeUrl; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.referrerPolicy = 'no-referrer'
  try { document.body.append(link); link.click() } catch {
    throw new ApiFailure('server', 'The attachment could not be opened. Request a fresh download.')
  } finally { link.remove() }
}
