import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'
import { ApiFailure, configurePrivateRequests } from '../src/api.ts'
import { downloadDocument, getDocument, getDocuments, localDownloadPath, retryDocument, uploadDocument, validateDocumentFile } from '../src/documentApi.ts'
import { attemptKey, documentId, documentRecord, fictionalFile, grant } from './document-fixtures.mjs'
import { deferred, otherWorkspaceId, page, workspaceId } from './auth-fixtures.mjs'
import { configureDocumentDownloads, externalDownloadUrl, openExternalDownload, s3DownloadOrigin } from '../src/documentDownloads.ts'

beforeEach(() => configurePrivateRequests({ workspaceId, accessToken: async () => 'synthetic-access-token', onFailure: () => {} }))
afterEach(() => { configurePrivateRequests(null); configureDocumentDownloads(null) })
const accepted = () => documentRecord({ state: 'accepted', detected_type: 'pdf', finished_at: '2026-11-14T12:00:00Z' })

test('upload sends exactly file multipart with browser boundary, bearer, workspace, key and 202 metadata', async (t) => {
  const file = fictionalFile()
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/documents'); assert.equal(options.method, 'POST')
    assert.equal(options.headers['Content-Type'], undefined)
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-token')
    assert.equal(options.headers['X-Workspace-ID'], workspaceId)
    assert.equal(options.headers['Idempotency-Key'], attemptKey)
    assert.ok(options.body instanceof FormData)
    assert.deepEqual([...options.body.keys()], ['file'])
    assert.equal(options.body.get('file').name, file.name)
    assert.equal(await options.body.get('file').text(), await file.text())
    assert.equal(options.redirect, 'error'); assert.equal(options.credentials, 'omit'); assert.equal(options.cache, 'no-store')
    return Response.json(documentRecord(), { status: 202 })
  })
  assert.equal((await uploadDocument(file, attemptKey)).state, 'queued')
})

test('terminal replay 200 is accepted and retry uses empty 202 POST without upload key', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/retry')) {
      assert.equal(options.body, undefined); assert.equal(options.headers['Content-Type'], undefined)
      assert.equal(options.headers['Idempotency-Key'], undefined)
      return Response.json(documentRecord(), { status: 202 })
    }
    return Response.json(accepted(), { status: 200 })
  })
  assert.equal((await uploadDocument(fictionalFile(), attemptKey)).state, 'accepted')
  assert.equal((await retryDocument(documentId)).state, 'queued')
})

test('list/recovery use real pagination fields and caller-scoped attempt selector', async (t) => {
  const paths = []
  t.mock.method(globalThis, 'fetch', async (url) => { paths.push(url); return Response.json(page([documentRecord()])) })
  await getDocuments({ limit: 20, offset: 0 }, {}, attemptKey)
  assert.equal(paths[0], `/api/documents?limit=20&offset=0&upload_attempt_key=${attemptKey}`)
  await assert.rejects(getDocument(documentId), ApiFailure) // A page is not detail metadata.
})

test('bad selection boundaries fail before dispatch; the server still validates contents', () => {
  assert.match(validateDocumentFile(null), /Choose one/)
  assert.match(validateDocumentFile(new File([], 'empty.pdf')), /1 to/)
  assert.equal(validateDocumentFile(new File([new Uint8Array(5000000)], 'fictional.png', { type: 'image/png' })), null)
  assert.match(validateDocumentFile(new File([new Uint8Array(5000001)], 'large.pdf')), /5,000,000/)
  for (const [name, type] of [['fictional.zip', 'application/zip'], ['fictional.pdf', 'text/html'], ['no-extension', 'image/png']]) assert.match(validateDocumentFile(new File(['fictional'], name, { type })), /PDF, JPEG or PNG/)
  assert.equal(validateDocumentFile(new File(['unvalidated'], 'fictional.PDF')), null)
})

for (const [status, code, kind] of [[413, 'validation_error', 'validation'], [415, 'validation_error', 'validation'], [409, 'conflict', 'conflict'], [503, 'service_unavailable', 'unavailable']]) {
  test(`upload handles safe ${status} without automatic write replay`, async (t) => {
    let calls = 0
    t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json({ error: { code, message: 'Safe synthetic failure.', details: [] } }, { status }) })
    await assert.rejects(uploadDocument(fictionalFile(), attemptKey), (error) => error.kind === kind && error.uncertainWrite === (status >= 500))
    assert.equal(calls, 1)
  })
}

test('late multipart response after workspace switch cannot populate the new workspace', async (t) => {
  const body = deferred(), started = deferred()
  let signal
  t.mock.method(globalThis, 'fetch', async (_, options) => { signal = options.signal; started.resolve(); return { ok: true, status: 202, json: () => body.promise } })
  const promise = uploadDocument(fictionalFile(), attemptKey)
  const cancelled = assert.rejects(promise, (error) => error.kind === 'cancelled' && error.uncertainWrite)
  await started.promise
  configurePrivateRequests({ workspaceId: otherWorkspaceId, accessToken: async () => 'next-synthetic-token', onFailure: () => {} })
  body.resolve(documentRecord()); await cancelled
  assert.equal(signal.aborted, true)
})

test('upload cancellation/timeout covers the full response and never resends', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return { ok: true, status: 202, json: () => new Promise(() => {}) } })
  await assert.rejects(uploadDocument(fictionalFile(), attemptKey, { timeoutMs: 15 }), (error) => error.kind === 'timeout' && error.uncertainWrite)
  assert.equal(calls, 1)
})

test('foreign-workspace and malformed document metadata are rejected', async (t) => {
  for (const record of [documentRecord({ workspace_id: otherWorkspaceId }), documentRecord({ state: 'approved' }), documentRecord({ can_retry: 'yes' }), documentRecord({ byte_size: 5000001 })]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(record))
    await assert.rejects(getDocument(documentId), (error) => error.kind === 'invalid-response')
  }
})

test('accepted download uses fresh empty grant POST, authenticated local GET, bounded bytes and generated attachment filename', async (t) => {
  const file = fictionalFile(), calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push(url)
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-token')
    assert.equal(options.headers['X-Workspace-ID'], workspaceId)
    if (url.endsWith('/download-url')) {
      assert.equal(options.method, 'POST'); assert.equal(options.body, undefined)
      assert.equal(options.headers['Idempotency-Key'], undefined)
      return Response.json(grant())
    }
    assert.equal(options.method, 'GET'); assert.equal(options.redirect, 'error')
    return new Response(file, { headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': `attachment; filename="document-${documentId}.pdf"` } })
  })
  const result = await downloadDocument(accepted())
  assert.equal(await result.blob.text(), await file.text())
  assert.equal(result.filename, `document-${documentId}.pdf`)
  assert.deepEqual(calls, [`/api/documents/${documentId}/download-url`, grant().url])
})

test('queued/rejected download requests never dispatch', async (t) => {
  t.mock.method(globalThis, 'fetch', () => assert.fail('Unaccepted bytes requested'))
  for (const state of ['queued', 'processing', 'receiving', 'rejected', 'failed']) await assert.rejects(downloadDocument(documentRecord({ state })), ApiFailure)
})

for (const url of ['https://storage.example.invalid/private?ticket=FICTIONAL', '//evil.invalid/x', `/api/documents/${documentId}/local-content?ticket=x&other=y`, `/api/documents/${documentId}/local-content?ticket=x#fragment`, '/api/documents/other/local-content?ticket=x']) {
  test('unsafe download destination is rejected without sending credentials: ' + url.split('?')[0], async (t) => {
    let calls = 0
    t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(grant({ url })) })
    await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'invalid-response')
    assert.equal(calls, 1)
    assert.throws(() => localDownloadPath(url, documentId), ApiFailure)
  })
}

test('workspace change between grant and content prevents a second fetch', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => {
    calls++
    configurePrivateRequests({ workspaceId: otherWorkspaceId, accessToken: async () => 'other-token', onFailure: () => {} })
    return Response.json(grant())
  })
  await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'cancelled')
  assert.equal(calls, 1)
})

test('local download bytes exceeding the limit are rejected even without trustworthy length', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url) => url.endsWith('/download-url') ? Response.json(grant())
    : new Response(new Uint8Array(5000001), { headers: { 'Content-Type': 'application/pdf' } }))
  await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'invalid-response')
})

test('uncertain processing retry sends one POST and can be recovered with a status GET', async (t) => {
  const methods = []
  t.mock.method(globalThis, 'fetch', async (_, options) => {
    methods.push(options.method)
    return options.method === 'POST' ? Response.json({ error: { code: 'service_unavailable', message: 'Synthetic unavailable', details: [] } }, { status: 503 }) : Response.json(documentRecord())
  })
  await assert.rejects(retryDocument(documentId), (error) => error.uncertainWrite)
  await getDocument(documentId)
  assert.deepEqual(methods, ['POST', 'GET'])
})

test('unconfigured external delivery and mismatched grant ownership never request bytes', async (t) => {
  for (const value of [grant({ delivery: 's3_presigned' }), grant({ workspace_id: otherWorkspaceId }), grant({ document_id: attemptKey })]) {
    let calls = 0
    t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(value) })
    await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'invalid-response')
    assert.equal(calls, 1)
  }
})

const s3Origin = 'https://siv-fictional-test.s3.eu-west-1.amazonaws.com'
const signedUrl = `${s3Origin}/isolated/documents/fictional?X-Amz-Signature=synthetic`
test('configured S3 grant makes only the authenticated grant request and never fetches external bytes', async (t) => {
  configureDocumentDownloads(s3Origin)
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push(url)
    assert.equal(url, `/api/documents/${documentId}/download-url`)
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-token')
    return Response.json(grant({ delivery: 's3_presigned', url: signedUrl }))
  })
  assert.deepEqual(await downloadDocument(accepted()), { delivery: 's3_presigned', url: signedUrl })
  assert.equal(calls.length, 1)
})

test('external grant ownership and delivery cannot bypass the configured origin check', async (t) => {
  configureDocumentDownloads(s3Origin)
  for (const value of [grant({ delivery: 's3_presigned', url: signedUrl, document_id: attemptKey }),
    grant({ delivery: 's3_presigned', url: signedUrl, workspace_id: otherWorkspaceId }),
    grant({ delivery: 'local_authenticated', url: signedUrl }), grant({ delivery: 'unknown', url: signedUrl })]) {
    let calls = 0
    t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(value) })
    await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'invalid-response')
    assert.equal(calls, 1)
  }
})

test('unexpected external destinations fail before any browser navigation or external fetch', async (t) => {
  configureDocumentDownloads(s3Origin)
  for (const url of ['http:' + signedUrl.slice(6), '//siv-fictional-test.s3.eu-west-1.amazonaws.com/x?s=x',
    signedUrl.replace('.com/', '.com.evil.invalid/'), signedUrl.replace('https://', 'https://user@'),
    signedUrl.replace('.com/', '.com:443/'), signedUrl + '#fragment', signedUrl.replace('/isolated', '\\isolated'),
    'https://other-bucket.s3.eu-west-1.amazonaws.com/file?signature=x', '/api/documents/x/local-content?ticket=x']) {
    let calls = 0
    t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(grant({ delivery: 's3_presigned', url })) })
    await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'invalid-response')
    assert.equal(calls, 1)
    assert.throws(() => externalDownloadUrl(url), ApiFailure)
  }
})

test('external origin must be an explicit supported HTTPS S3 origin without path, port or query', () => {
  for (const value of [null, '', 'https://storage.example.invalid', s3Origin + '/', s3Origin + ':443', s3Origin + '?x=y', s3Origin.replace('https:', 'http:')]) assert.equal(s3DownloadOrigin(value), null)
  assert.equal(s3DownloadOrigin(s3Origin), s3Origin)
})

test('S3 navigation uses a disposable anchor with no opener, referrer or app headers', (t) => {
  configureDocumentDownloads(s3Origin)
  const actions = [], link = { click() { actions.push('click') }, remove() { actions.push('remove') } }
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'document')
  Object.defineProperty(globalThis, 'document', { value: { createElement: (tag) => { assert.equal(tag, 'a'); return link }, body: { append: (element) => { assert.equal(element, link); actions.push('append') } } }, configurable: true })
  t.after(() => { if (previous) Object.defineProperty(globalThis, 'document', previous); else delete globalThis.document })
  t.mock.method(globalThis, 'fetch', () => assert.fail('S3 navigation must never fetch'))
  openExternalDownload(signedUrl)
  assert.equal(link.href, signedUrl); assert.equal(link.target, '_blank')
  assert.equal(link.rel, 'noopener noreferrer'); assert.equal(link.referrerPolicy, 'no-referrer')
  assert.deepEqual(actions, ['append', 'click', 'remove'])
  assert.equal(link.headers, undefined)
  assert.throws(() => openExternalDownload('https://evil.invalid/file?x=y'), ApiFailure)
  assert.deepEqual(actions, ['append', 'click', 'remove'])
})

test('workspace change or cancellation while obtaining an external grant prevents delivery', async (t) => {
  configureDocumentDownloads(s3Origin)
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => {
    calls++
    configurePrivateRequests({ workspaceId: otherWorkspaceId, accessToken: async () => 'other-token', onFailure: () => {} })
    return Response.json(grant({ delivery: 's3_presigned', url: signedUrl }))
  })
  await assert.rejects(downloadDocument(accepted()), (error) => error.kind === 'cancelled')
  assert.equal(calls, 1)
})

test('attachment body timeout cancels streaming and is never an uncertain write', async (t) => {
  let cancelled = false
  t.mock.method(globalThis, 'fetch', async (url) => url.endsWith('/download-url') ? Response.json(grant())
    : new Response(new ReadableStream({ cancel() { cancelled = true } }), { headers: { 'Content-Type': 'application/pdf' } }))
  await assert.rejects(downloadDocument(accepted(), { timeoutMs: 15 }), (error) => error.kind === 'timeout' && !error.uncertainWrite)
  assert.equal(cancelled, true)
})
