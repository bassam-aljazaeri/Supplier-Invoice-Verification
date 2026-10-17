import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { ApiFailure, configurePrivateRequests, createSupplier, getSuppliers, privateContextVersion } from '../src/api.ts'
import { addMembership, changeMembership, createWorkspace, getMe, getMemberships, removeMembership } from '../src/accountApi.ts'
import { createRequestScope } from '../src/requestScope.ts'
import { deferred, flush, harness, identity, me, membership, otherWorkspaceId, page, supplier, timestamp, userId, workspaceId } from './auth-fixtures.mjs'

afterEach(() => configurePrivateRequests(null))
const authority = (workspace = workspaceId, onFailure = () => {}) => configurePrivateRequests({ workspaceId: workspace, accessToken: async () => 'synthetic-access-only', onFailure })
const rejected = (status) => Response.json({ error: { code: status === 401 ? 'unauthorized' : status === 403 ? 'forbidden' : status === 409 ? 'conflict' : 'service_unavailable', message: 'synthetic-private-provider-detail', details: [] } }, { status })

test('private requests fail before transport while signed out or without a selected workspace', async (t) => {
  t.mock.method(globalThis, 'fetch', () => assert.fail('No unauthenticated private request may dispatch.'))
  await assert.rejects(getSuppliers(), (error) => error.kind === 'unauthorized' && !error.uncertainWrite)
  authority(null)
  await assert.rejects(getSuppliers(), (error) => error.kind === 'forbidden')
})
test('business requests send only access bearer and selected workspace to same-origin proxy', async (t) => {
  authority()
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/suppliers?limit=20&offset=0')
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-only')
    assert.equal(options.headers['X-Workspace-ID'], workspaceId)
    assert.equal(options.credentials, 'omit'); assert.equal(options.redirect, 'error')
    assert.equal('X-Role' in options.headers, false)
    return Response.json(page([supplier()]))
  })
  assert.equal((await getSuppliers()).items[0].workspace_id, workspaceId)
})
test('an unexpected response workspace is rejected instead of displayed', async (t) => {
  authority()
  t.mock.method(globalThis, 'fetch', async () => Response.json(page([supplier(otherWorkspaceId)])))
  await assert.rejects(getSuppliers(), (error) => error.kind === 'invalid-response')
})
test('identity and membership APIs never send a competing workspace header', async (t) => {
  authority()
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push([url, options])
    assert.equal(options.headers['X-Workspace-ID'], undefined)
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-only')
    if (url === '/api/me') return Response.json(me())
    if (options.method === 'DELETE') return new Response(null, { status: 204 })
    if (options.method === 'GET') return Response.json(page([membership()]))
    return Response.json(membership(), { status: options.method === 'POST' ? 201 : 200 })
  })
  assert.equal((await getMe()).user.id, userId)
  await getMemberships(workspaceId)
  await addMembership(workspaceId, userId, 'approver')
  await changeMembership(workspaceId, userId, 'accountant')
  assert.equal(await removeMembership(workspaceId, userId), undefined)
  assert.deepEqual(calls.map(([, options]) => options.method), ['GET', 'GET', 'POST', 'PATCH', 'DELETE'])
  assert.deepEqual(JSON.parse(calls[2][1].body), { application_user_id: userId, role: 'approver' })
  assert.deepEqual(JSON.parse(calls[3][1].body), { role: 'accountant' })
})
test('onboarding exposes own ID with no memberships and never grants demo access', async (t) => {
  const h = harness(t, { loadMe: async () => me([]) })
  await h.start()
  assert.equal(h.session.snapshot().me.user.id, userId)
  assert.deepEqual(h.session.snapshot().me.memberships, [])
  assert.equal(h.session.snapshot().selected, null)
})
test('workspace creation uses the actual atomic response contract and no selection header', async (t) => {
  authority(null)
  const member = membership()
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/workspaces'); assert.equal(options.headers['X-Workspace-ID'], undefined)
    assert.deepEqual(JSON.parse(options.body), { slug: 'synthetic-team', name: 'Synthetic team' })
    return Response.json({ workspace: member.workspace, membership: member }, { status: 201 })
  })
  assert.equal((await createWorkspace({ slug: ' synthetic-team ', name: ' Synthetic team ' })).membership.role, 'administrator')
})
test('invalid workspace or onboarding user inputs never dispatch writes', async (t) => {
  authority()
  t.mock.method(globalThis, 'fetch', () => assert.fail('Invalid input dispatched.'))
  for (const slug of ['local-demo', 'Bad Name', 'bad--slug', '-bad']) await assert.rejects(createWorkspace({ slug, name: 'Synthetic' }), ApiFailure)
  await assert.rejects(addMembership(workspaceId, 'email@example.invalid', 'approver'), ApiFailure)
  await assert.rejects(changeMembership(workspaceId, userId, 'owner'), ApiFailure)
})
test('multiple accessible workspaces require an explicit valid selection', async (t) => {
  const h = harness(t, { loadMe: async () => me([membership(), membership(otherWorkspaceId, 'approver')]) })
  await h.start()
  assert.equal(h.session.snapshot().selected, null)
  h.session.selectWorkspace('00000000-0000-4000-8000-000000000099')
  assert.equal(h.session.snapshot().selected, null)
  h.session.selectWorkspace(otherWorkspaceId)
  assert.equal(h.session.snapshot().selected.role, 'approver')
})
test('workspace switch cancels pending reads and old bodies cannot restore records', async (t) => {
  const h = harness(t, { loadMe: async () => me([membership(), membership(otherWorkspaceId)]) })
  await h.start(); h.session.selectWorkspace(workspaceId)
  const body = deferred(), started = deferred()
  let signal
  t.mock.method(globalThis, 'fetch', async (_, options) => { signal = options.signal; started.resolve(); return { status: 200, ok: true, json: () => body.promise } })
  const read = getSuppliers()
  const failure = assert.rejects(read, (error) => error.kind === 'cancelled')
  await started.promise
  const oldVersion = h.session.snapshot().version
  h.session.selectWorkspace(otherWorkspaceId)
  assert.equal(signal.aborted, true)
  body.resolve(page([supplier()])); await failure
  assert.ok(h.session.snapshot().version > oldVersion)
  assert.equal(h.session.snapshot().selected.workspace_id, otherWorkspaceId)
})
test('dispatched write interruption warns for its original workspace and never replays', async (t) => {
  const h = harness(t, { loadMe: async () => me([membership(), membership(otherWorkspaceId)]) })
  await h.start(); h.session.selectWorkspace(workspaceId)
  const started = deferred(), body = deferred(); let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; started.resolve(); return { status: 201, ok: true, json: () => body.promise } })
  const write = createSupplier({ supplier_code: 'SYNTHETIC', name: 'Synthetic supplier' })
  const failure = assert.rejects(write, (error) => error.kind === 'cancelled' && error.uncertainWrite)
  await started.promise; h.session.selectWorkspace(otherWorkspaceId)
  assert.match(h.session.snapshot().warning, new RegExp(workspaceId))
  body.resolve(supplier()); await failure
  assert.equal(calls, 1)
})
test('request completion scopes include session/workspace generation before React unmount', () => {
  authority()
  const scope = createRequestScope(privateContextVersion), request = scope.start()
  assert.equal(scope.isCurrent(request), true)
  authority(otherWorkspaceId)
  assert.equal(scope.isCurrent(request), false)
  assert.equal(scope.isCurrent(scope.start()), true)
})
test('uncertain write warning survives a completed timeout before switching workspace', async (t) => {
  const h = harness(t, { loadMe: async () => me([membership(), membership(otherWorkspaceId)]) })
  await h.start(); h.session.selectWorkspace(workspaceId)
  t.mock.method(globalThis, 'fetch', () => new Promise(() => {}))
  await assert.rejects(createSupplier({ supplier_code: 'SYNTHETIC', name: 'Synthetic' }, { timeoutMs: 15 }), (error) => error.uncertainWrite)
  h.session.selectWorkspace(otherWorkspaceId)
  assert.match(h.session.snapshot().warning, new RegExp(workspaceId))
})
test('HTTP 401 ends identity and workspace state, with no retry or provider error disclosure', async (t) => {
  const h = harness(t)
  await h.start(); let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return rejected(401) })
  await assert.rejects(getSuppliers(), (error) => error.kind === 'unauthorized' && !error.message.includes('synthetic-private'))
  assert.equal(h.session.snapshot().status, 'signed-out')
  assert.equal(h.session.snapshot().me, null); assert.equal(h.session.snapshot().selected, null)
  assert.equal(calls, 1)
})
test('HTTP 403 refreshes current roles, clears old views and never retries a POST', async (t) => {
  let graph = me(), refreshes = 0, calls = 0
  const h = harness(t, { loadMe: async () => { refreshes++; return graph } })
  await h.start(); const oldVersion = h.session.snapshot().version
  graph = me([membership(workspaceId, 'approver')])
  t.mock.method(globalThis, 'fetch', async () => { calls++; return rejected(403) })
  await assert.rejects(createSupplier({ supplier_code: 'SYNTHETIC', name: 'Synthetic supplier' }), (error) => error.kind === 'forbidden')
  await flush()
  assert.equal(h.session.snapshot().status, 'ready'); assert.equal(h.session.snapshot().selected.role, 'approver')
  assert.ok(h.session.snapshot().version > oldVersion)
  assert.equal(calls, 1); assert.equal(refreshes, 2)
  assert.equal(h.session.snapshot().warning, null)
})
test('membership loss clears workspace selection and blocks subsequent business dispatch', async (t) => {
  let graph = me()
  const h = harness(t, { loadMe: async () => graph })
  await h.start(); graph = me([])
  await h.session.refreshAccess()
  assert.equal(h.session.snapshot().selected, null)
  t.mock.method(globalThis, 'fetch', () => assert.fail('Lost membership still dispatched.'))
  await assert.rejects(getSuppliers(), (error) => error.kind === 'forbidden')
})
test('JWKS/service 503 permits recovery without logging out or replaying the request', async (t) => {
  const h = harness(t); await h.start(); let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return rejected(503) })
  await assert.rejects(getSuppliers(), (error) => error.kind === 'unavailable')
  assert.equal(h.session.snapshot().status, 'ready'); assert.equal(calls, 1)
})
test('membership 409 remains a clear conflict and does not retry or lose authentication', async (t) => {
  const h = harness(t); await h.start(); let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return rejected(409) })
  await assert.rejects(changeMembership(workspaceId, userId, 'approver'), (error) => error.kind === 'conflict' && error.status === 409)
  assert.equal(calls, 1); assert.equal(h.session.snapshot().status, 'ready')
})
test('coalesced pre-expiry renewal happens before dispatch and replaces the access token', async (t) => {
  const next = deferred(); let renewals = 0, token = 'synthetic-access-one'
  const h = harness(t, { client: { renew: async () => { renewals++; await next.promise; token = 'synthetic-access-two'; return identity() }, accessToken: () => token } })
  await h.start(); h.signed.expiresAt = Date.now() / 1000 + 10
  let calls = 0
  t.mock.method(globalThis, 'fetch', async (_, options) => { calls++; assert.equal(options.headers.Authorization, 'Bearer synthetic-access-two'); return Response.json(page([])) })
  const first = getSuppliers(), second = getSuppliers()
  assert.equal(calls, 0); await flush(); assert.equal(renewals, 1)
  next.resolve(); await Promise.all([first, second])
  assert.equal(calls, 2)
})
test('failed or unavailable renewal ends session before dispatch without a login loop', async (t) => {
  const h = harness(t, { client: { renew: async () => { throw new Error('synthetic-refresh-secret') } } })
  await h.start(); h.signed.expiresAt = Date.now() / 1000 + 10
  t.mock.method(globalThis, 'fetch', () => assert.fail('Failed renewal dispatched a business request.'))
  await assert.rejects(getSuppliers())
  assert.equal(h.session.snapshot().status, 'signed-out')
  assert.doesNotMatch(h.session.snapshot().message, /synthetic-refresh-secret/)
  assert.equal(h.events.some((e) => Array.isArray(e) && e[0] === 'external'), false)
})
test('renewal deadline and late completion cannot restore a discarded session', async (t) => {
  const next = deferred()
  const h = harness(t, { deadline: 15, client: { renew: () => next.promise } })
  await h.start(); h.signed.expiresAt = Date.now() / 1000 + 1
  await assert.rejects(getSuppliers())
  assert.equal(h.session.snapshot().status, 'signed-out')
  next.resolve(identity()); await flush()
  assert.equal(h.session.snapshot().me, null)
})
test('changed renewal subject ends the session', async (t) => {
  const h = harness(t, { client: { renew: async () => ({ ...identity(), subject: 'different-subject' }) } })
  await h.start(); h.signed.expiresAt = Date.now() / 1000 + 1
  await assert.rejects(getSuppliers())
  assert.equal(h.session.snapshot().status, 'signed-out')
})
test('a save timed out before renewal finishes cannot dispatch later or replay itself', async (t) => {
  const next = deferred(), h = harness(t, { client: { renew: () => next.promise } })
  await h.start(); h.signed.expiresAt = Date.now() / 1000 + 1
  t.mock.method(globalThis, 'fetch', () => assert.fail('Timed-out save dispatched after renewal.'))
  await assert.rejects(createSupplier({ supplier_code: 'SYNTHETIC', name: 'Synthetic' }, { timeoutMs: 15 }), (error) => error.kind === 'timeout' && !error.uncertainWrite)
  next.resolve(identity()); await flush()
  assert.equal(h.session.snapshot().status, 'ready')
})
test('a membership response for another workspace is rejected before rendering', async (t) => {
  authority()
  t.mock.method(globalThis, 'fetch', async () => Response.json(page([membership(otherWorkspaceId)])))
  await assert.rejects(getMemberships(workspaceId), (error) => error.kind === 'invalid-response')
})
test('logout during renewal blocks late API dispatch and session resurrection', async (t) => {
  const next = deferred(), h = harness(t, { client: { renew: () => next.promise } })
  await h.start(); h.signed.expiresAt = Date.now() / 1000 + 1
  const read = getSuppliers(); const failure = assert.rejects(read)
  await flush(); await h.session.logout(); next.resolve(identity()); await failure; await flush()
  assert.equal(h.session.snapshot().me, null); assert.equal(h.session.snapshot().selected, null)
})
test('late identity refresh after logout cannot populate a new context', async (t) => {
  let graph = Promise.resolve(me())
  const h = harness(t, { loadMe: () => graph })
  await h.start()
  const next = deferred(); graph = next.promise
  const refreshing = h.session.refreshAccess()
  await h.session.logout(); next.resolve(me()); await refreshing
  assert.equal(h.session.snapshot().me, null)
})
test('API identity mismatch is denied and cannot merge users', async (t) => {
  const h = harness(t, { loadMe: async () => ({ ...me(), user: { ...me().user, subject: 'different-subject' } }) })
  await h.start()
  assert.equal(h.session.snapshot().status, 'signed-out'); assert.equal(h.session.snapshot().me, null)
})
test('malformed membership and user response fields fail validation', async (t) => {
  authority()
  t.mock.method(globalThis, 'fetch', async () => Response.json({ ...me(), memberships: [{ ...membership(), application_user_id: 'other-user' }] }))
  await assert.rejects(getMe(), (error) => error.kind === 'invalid-response')
})
test('refresh-access failure is recoverable without automatic requests or lost identity tokens', async (t) => {
  let failed = true
  const h = harness(t, { loadMe: async () => { if (failed) throw new ApiFailure('unavailable', 'Synthetic unavailable'); return me() } })
  await h.start()
  assert.equal(h.session.snapshot().status, 'access-error')
  failed = false; await h.session.refreshAccess()
  assert.equal(h.session.snapshot().status, 'ready')
})
test('refresh uses current timestamps and roles rather than client role headers', async (t) => {
  const h = harness(t, { loadMe: async () => me([membership(workspaceId, 'accountant')]) })
  await h.start()
  assert.equal(h.session.snapshot().selected.role, 'accountant')
  assert.equal(h.session.snapshot().selected.updated_at, timestamp)
})
