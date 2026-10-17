import assert from 'node:assert/strict'
import { test } from 'node:test'
import { InMemoryWebStorage } from 'oidc-client-ts'
import { readAuthConfig } from '../src/authConfig.ts'
import { bounded, clearLoginState, cognitoLogoutUrl, createAuthClient, oidcSettings, STATE_PREFIX, validateMetadata } from '../src/auth.ts'
import { safeReturnHash } from '../src/navigation.ts'
import { canCreate, canManage } from '../src/authTypes.ts'
import { configuration, deferred, flush, harness, me, publicSettings } from './auth-fixtures.mjs'

test('missing settings are useful and do not disclose supplied values', () => {
  const result = readAuthConfig({ VITE_COGNITO_CLIENT_ID: 'synthetic-sensitive-sentinel' })
  assert.equal(result.config, null)
  assert.match(result.error, /VITE_COGNITO_AUTHORITY/)
  assert.doesNotMatch(result.error, /synthetic-sensitive-sentinel/)
  assert.ok(configuration.config)
})
for (const [key, value] of [
  ['VITE_COGNITO_AUTHORITY', 'http://untrusted.invalid/pool'],
  ['VITE_COGNITO_AUTHORITY', publicSettings.VITE_COGNITO_AUTHORITY + '/'],
  ['VITE_COGNITO_AUTHORITY', 'https://cognito-idp.eu-west-1.amazonaws.com/us-east-1_WRONG'],
  ['VITE_COGNITO_DOMAIN', 'https://user:secret@untrusted.invalid'],
  ['VITE_COGNITO_DOMAIN', publicSettings.VITE_COGNITO_DOMAIN + '/path'],
  ['VITE_COGNITO_CLIENT_ID', 'client secret with spaces'],
  ['VITE_AUTH_CALLBACK_URL', 'http://localhost:5173/#/auth/callback'],
  ['VITE_AUTH_CALLBACK_URL', 'http://127.0.0.1:5173/auth/callback'],
  ['VITE_AUTH_LOGOUT_URL', 'https://external.invalid/'],
]) test(`invalid ${key} fails closed with setup guidance`, () => assert.equal(readAuthConfig({ ...publicSettings, [key]: value }).config, null))

test('OIDC settings explicitly separate memory tokens from transient session state', async () => {
  const transient = new InMemoryWebStorage(), memory = new InMemoryWebStorage()
  const settings = oidcSettings(configuration.config, transient, memory)
  assert.equal(settings.response_type, 'code'); assert.equal(settings.response_mode, 'query')
  assert.equal(settings.disablePKCE, false); assert.equal(settings.automaticSilentRenew, false)
  assert.equal(settings.monitorSession, false); assert.equal(settings.loadUserInfo, false)
  assert.equal(settings.validateSubOnSilentRenew, true)
  assert.deepEqual(settings.revokeTokenTypes, ['refresh_token'])
  await settings.userStore.set('user', 'synthetic-token-sentinel')
  assert.equal(transient.length, 0); assert.equal(memory.length, 1)
  await settings.stateStore.set('attempt', 'synthetic-pkce-sentinel')
  transient.setItem('other-app', 'untouched')
  clearLoginState(transient)
  assert.equal(transient.length, 1); assert.equal(transient.getItem('other-app'), 'untouched')
})

for (const value of ['https://external.invalid/', '//external.invalid', '#//external.invalid', '#/unknown', '#/signin', '#/account?return=https://external.invalid', '#/suppliers\\evil', '#/status\n']) {
  test('unsafe return navigation is replaced with Account', () => assert.equal(safeReturnHash(value), '#/account'))
}
test('only known internal hash routes survive return navigation', () => {
  assert.equal(safeReturnHash('#/invoices?limit=20&offset=40'), '#/invoices?limit=20&offset=40')
  assert.equal(safeReturnHash('#/workspaces/new'), '#/workspaces/new')
})
test('role policies permit read-only approvers and admin-only membership controls', () => {
  assert.equal(canCreate('administrator'), true); assert.equal(canCreate('accountant'), true)
  assert.equal(canCreate('approver'), false); assert.equal(canCreate(undefined), false)
  assert.equal(canManage('administrator'), true)
  assert.equal(canManage('accountant'), false); assert.equal(canManage('approver'), false)
})
test('callback is coalesced outside StrictMode and strips its URL before processing', async (t) => {
  let calls = 0
  const h = harness(t, { client: { callback: async () => { calls++; assert.equal(h.events[0], 'strip-query'); return h.signed } } })
  const first = h.start(), second = h.start()
  assert.equal(first, second)
  await Promise.all([first, second])
  assert.equal(calls, 1); assert.equal(h.session.snapshot().status, 'ready')
  assert.deepEqual(h.events.at(-1), ['replace', '#/account'])
})
test('successful callback survives the runtime internal hashchange and keeps access usable', async (t) => {
  const navigation = new EventTarget()
  let returns = 0
  const h = harness(t, { host: { replace: () => {
    returns++
    navigation.dispatchEvent(new Event('hashchange'))
  } } })
  navigation.addEventListener('hashchange', h.session.cancelPending)
  t.after(() => navigation.removeEventListener('hashchange', h.session.cancelPending))
  await Promise.all([h.start(), h.start()])
  assert.equal(returns, 1)
  assert.equal(h.session.snapshot().status, 'ready')
  assert.equal(h.session.snapshot().me.user.id, me().user.id)
  assert.equal(h.session.snapshot().selected.workspace_id, me().memberships[0].workspace_id)
  const { getSuppliers } = await import('../src/api.ts')
  t.mock.method(globalThis, 'fetch', async (_, options) => {
    assert.equal(options.headers.Authorization, 'Bearer synthetic-access-token')
    assert.equal(options.headers['X-Workspace-ID'], me().memberships[0].workspace_id)
    return Response.json({ items: [], limit: 20, offset: 0, total: 0 })
  })
  assert.deepEqual((await getSuppliers()).items, [])
})
test('cancelled callback cannot restore identity or navigate after leaving', async (t) => {
  const pending = deferred()
  const h = harness(t, { client: { callback: () => pending.promise } })
  const completion = h.start()
  h.session.cancelPending(); pending.resolve(h.signed)
  await completion
  assert.equal(h.session.snapshot().status, 'signed-out'); assert.equal(h.session.snapshot().me, null)
  assert.equal(h.events.some((e) => Array.isArray(e)), false)
})
test('leaving during callback identity loading prevents its late redirect', async (t) => {
  const pending = deferred()
  const h = harness(t, { loadMe: () => pending.promise })
  const completion = h.start(); await flush()
  assert.equal(h.session.snapshot().status, 'loading')
  h.session.cancelPending(); pending.resolve(me()); await completion
  assert.equal(h.session.snapshot().me, null)
  assert.equal(h.events.some((e) => Array.isArray(e) && e[0] === 'replace'), false)
})
test('callback failure is sanitized, bounded and requires explicit retry', async (t) => {
  const pending = deferred()
  const h = harness(t, { deadline: 15, client: { callback: () => pending.promise } })
  await h.start()
  assert.equal(h.session.snapshot().status, 'signed-out')
  pending.resolve(h.signed); await flush()
  assert.equal(h.session.snapshot().me, null)
  assert.equal(h.events.some((e) => Array.isArray(e) && e[0] === 'external'), false)
})
test('numeric host never creates login state or redirects to Cognito', async (t) => {
  let called = false
  const h = harness(t, { host: { origin: () => 'http://127.0.0.1:5173' }, client: { signIn: async () => { called = true } } })
  await h.session.signIn('#/account')
  assert.equal(called, false); assert.match(h.session.snapshot().message, /localhost:5173/)
})
test('late sign-in URL after cancellation cannot redirect', async (t) => {
  const pending = deferred()
  const h = harness(t, { client: { signIn: () => pending.promise } })
  const completion = h.session.signIn('#/account')
  h.session.cancelPending(); pending.resolve(configuration.config.domain + '/oauth2/authorize')
  await completion
  assert.equal(h.events.some((e) => Array.isArray(e) && e[0] === 'external'), false)
})
test('unsafe authorization navigation is rejected and failure does not leak provider details', async (t) => {
  const h = harness(t, { client: { signIn: async () => 'https://external.invalid/synthetic-token-sentinel' } })
  await h.session.signIn('#/account')
  assert.equal(h.session.snapshot().status, 'signed-out')
  assert.doesNotMatch(h.session.snapshot().message, /synthetic-token-sentinel/)
})
test('reload starts signed out and clears abandoned transient state without automatic redirects', async (t) => {
  const h = harness(t)
  h.storage.setItem(STATE_PREFIX + 'abandoned', 'synthetic-state')
  await h.session.start('http://localhost:5173/#/invoices')
  assert.equal(h.session.snapshot().status, 'signed-out'); assert.equal(h.storage.length, 0)
  assert.equal(h.events.some((e) => Array.isArray(e)), false)
})
test('missing configuration still strips callback secrets and leaves setup usable', async (t) => {
  const h = harness(t, { configuration: readAuthConfig({}) })
  await h.start()
  assert.equal(h.events[0], 'strip-query'); assert.equal(h.session.snapshot().status, 'setup')
})
test('logout clears shared identity first and invokes only Cognito logout parameters', async (t) => {
  const pending = deferred()
  const h = harness(t, { client: { takeRevocation: () => () => pending.promise } })
  await h.start()
  const completion = h.session.logout()
  assert.equal(h.session.snapshot().me, null); assert.equal(h.session.snapshot().selected, null)
  assert.ok(h.events.includes('clear-user'))
  pending.reject(new Error('synthetic-provider-secret'))
  await completion
  const url = new URL(h.events.at(-1)[1])
  assert.equal(url.pathname, '/logout')
  assert.deepEqual([...url.searchParams.keys()], ['client_id', 'logout_uri'])
  assert.equal(url.searchParams.get('logout_uri'), 'http://localhost:5173/')
  assert.doesNotMatch(h.session.snapshot().message, /synthetic-provider-secret/)
})
test('leaving during best-effort revocation prevents a late logout redirect', async (t) => {
  const pending = deferred(), h = harness(t, { client: { takeRevocation: () => () => pending.promise } })
  await h.start()
  const completion = h.session.logout(); h.session.cancelPending(); pending.resolve(); await completion
  assert.equal(h.events.some((e) => Array.isArray(e) && e[0] === 'external'), false)
  assert.equal(h.session.snapshot().status, 'signed-out')
})
test('best-effort revocation has a total bound and cannot retain shared session state', async (t) => {
  const h = harness(t, { deadline: 15, client: { takeRevocation: () => () => new Promise(() => {}) } })
  await h.start(); await h.session.logout()
  assert.equal(h.session.snapshot().me, null)
  assert.equal(h.events.at(-1)[1], cognitoLogoutUrl(configuration.config))
})
test('bounded auth work times out without printing internal failures', async () => {
  await assert.rejects(bounded(new Promise(() => {}), 10), /deadline/)
})

const metadata = () => ({
  issuer: configuration.config.authority,
  authorization_endpoint: configuration.config.domain + '/oauth2/authorize',
  token_endpoint: configuration.config.domain + '/oauth2/token',
  revocation_endpoint: configuration.config.domain + '/oauth2/revoke',
  jwks_uri: configuration.config.authority + '/.well-known/jwks.json',
})
test('discovery endpoint values are pinned to the configured pool and login domain', () => {
  validateMetadata(metadata(), configuration.config)
  for (const key of Object.keys(metadata())) assert.throws(() => validateMetadata({ ...metadata(), [key]: 'https://external.invalid/' }, configuration.config))
})
function idToken(nonce, subject = 'synthetic-subject') {
  // A synthetic decoded ID-token fixture for library protocol tests, not a JWT
  // signature test or a claim that real Cognito accepted this flow.
  return [Buffer.from(JSON.stringify({ alg: 'RS256' })).toString('base64url'), Buffer.from(JSON.stringify({ iss: configuration.config.authority, aud: configuration.config.clientId, sub: subject, nonce, iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 900 })).toString('base64url'), 'synthetic-signature'].join('.')
}
async function protocolHarness(t, options = {}) {
  const storage = new InMemoryWebStorage(), requests = []
  let nonce, refreshes = 0
  t.mock.method(globalThis, 'fetch', async (url, request) => {
    requests.push([url, request])
    if (url === configuration.config.authority + '/.well-known/openid-configuration') return Response.json(metadata())
    assert.equal(url, configuration.config.domain + '/oauth2/token')
    const form = new URLSearchParams(request.body)
    if (form.get('grant_type') === 'refresh_token') {
      assert.equal(form.get('refresh_token'), 'synthetic-refresh-one'); refreshes++
    } else {
      assert.equal(form.get('grant_type'), 'authorization_code')
      assert.ok(form.get('code_verifier')); assert.equal(form.get('redirect_uri'), configuration.config.callbackUrl)
    }
    return Response.json({ id_token: idToken(options.badNonce ? 'wrong-nonce' : nonce, options.subject), access_token: refreshes ? 'synthetic-access-two' : 'synthetic-access-one', refresh_token: options.noRefresh ? undefined : refreshes ? 'synthetic-refresh-two' : 'synthetic-refresh-one', token_type: 'Bearer', expires_in: 900, scope: 'openid' })
  })
  const client = createAuthClient(configuration.config, storage)
  t.after(() => client.clear())
  const authorize = new URL(await client.signIn('#/invoices'))
  nonce = authorize.searchParams.get('nonce')
  return { client, storage, requests, authorize, callback: configuration.config.callbackUrl + '?code=synthetic-code&state=' + authorize.searchParams.get('state') }
}
test('real library generates PKCE/nonce/state and consumes one callback; tokens remain outside sessionStorage', async (t) => {
  const h = await protocolHarness(t)
  assert.equal(h.authorize.searchParams.get('response_type'), 'code')
  assert.equal(h.authorize.searchParams.get('code_challenge_method'), 'S256')
  assert.ok(h.authorize.searchParams.get('code_challenge')); assert.ok(h.authorize.searchParams.get('nonce'))
  assert.equal(new URL(h.authorize.searchParams.get('redirect_uri')).hash, '')
  assert.equal(h.storage.length, 1)
  const signed = await h.client.callback(h.callback)
  assert.equal(signed.subject, 'synthetic-subject'); assert.equal(signed.returnHash, '#/invoices')
  assert.equal(h.client.accessToken(), 'synthetic-access-one'); assert.equal(h.storage.length, 0)
  await assert.rejects(h.client.callback(h.callback))
})
test('real library rejects mismatched state and nonce', async (t) => {
  const h = await protocolHarness(t, { badNonce: true })
  await assert.rejects(h.client.callback(configuration.config.callbackUrl + '?code=synthetic&state=wrong-state'))
  await assert.rejects(h.client.callback(h.callback), /nonce/)
  assert.equal(h.client.accessToken(), null)
})
test('real library uses refresh-token grant, rotates memory tokens and never needs an iframe', async (t) => {
  const h = await protocolHarness(t)
  await h.client.callback(h.callback)
  await h.client.renew()
  assert.equal(h.client.accessToken(), 'synthetic-access-two'); assert.equal(h.storage.length, 0)
  assert.equal(h.requests.filter(([, request]) => request?.body && new URLSearchParams(request.body).get('grant_type') === 'refresh_token').length, 1)
})
test('missing in-memory refresh token rejects renewal before any iframe or network request', async (t) => {
  const h = await protocolHarness(t, { noRefresh: true })
  await h.client.callback(h.callback)
  const before = h.requests.length
  await assert.rejects(h.client.renew())
  assert.equal(h.requests.length, before)
})
test('denied login consumes transient correlation state without creating a session', async (t) => {
  const h = await protocolHarness(t)
  await assert.rejects(h.client.callback(configuration.config.callbackUrl + '?error=access_denied&error_description=synthetic-private-detail&state=' + h.authorize.searchParams.get('state')))
  assert.equal(h.storage.length, 0); assert.equal(h.client.accessToken(), null)
})
test('transient login state older than fifteen minutes cannot authorize a callback', async (t) => {
  const h = await protocolHarness(t)
  const key = h.storage.key(0), state = JSON.parse(h.storage.getItem(key))
  state.created = Math.floor(Date.now() / 1000) - 901
  h.storage.setItem(key, JSON.stringify(state))
  await assert.rejects(h.client.callback(h.callback))
  assert.equal(h.storage.length, 0); assert.equal(h.client.accessToken(), null)
})
test('late library token completion remains in its discarded manager after cleanup', async (t) => {
  const h = await protocolHarness(t)
  const original = globalThis.fetch, pending = deferred(), started = deferred()
  t.mock.method(globalThis, 'fetch', async (...args) => { const response = await original(...args); started.resolve(); await pending.promise; return response })
  const completion = h.client.callback(h.callback)
  await started.promise; h.client.clear(); pending.resolve()
  await assert.rejects(completion)
  assert.equal(h.client.accessToken(), null); assert.equal(h.storage.length, 0)
})
test('logout capsule revokes only the latest refresh token after memory cleanup', async (t) => {
  const h = await protocolHarness(t)
  await h.client.callback(h.callback); await h.client.renew()
  const revoke = h.client.takeRevocation()
  h.client.clear(); assert.equal(h.client.accessToken(), null)
  let calls = 0
  t.mock.method(globalThis, 'fetch', async (url, request) => {
    calls++; assert.equal(url, configuration.config.domain + '/oauth2/revoke')
    const form = new URLSearchParams(request.body)
    assert.equal(form.get('token_type_hint'), 'refresh_token')
    assert.equal(form.get('token'), 'synthetic-refresh-two')
    return new Response(null, { status: 200 })
  })
  await revoke(); assert.equal(calls, 1); assert.equal(h.client.accessToken(), null)
})
