import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer, loadConfigFromFile } from 'vite'
import { me, membership, workspaceId } from './auth-fixtures.mjs'

let server, context, components, originalWindow
before(async () => {
  const root = fileURLToPath(new URL('../', import.meta.url))
  const loaded = await loadConfigFromFile({ command: 'serve', mode: 'test' }, root + 'vite.config.ts')
  assert.equal(loaded.config.server.host, 'localhost')
  assert.equal(loaded.config.server.proxy['/api'].target, 'http://127.0.0.1:8000')
  // Never load any actual environment file, even if one is present on the host.
  server = await createServer({ ...loaded.config, root, configFile: false, envDir: false, logLevel: 'silent', server: { ...loaded.config.server, port: 0, hmr: false } })
  await server.listen()
  context = (await server.ssrLoadModule('/src/authContext.tsx')).SessionContext
  components = await Promise.all([
    '/src/components/Navigation.tsx', '/src/components/WorkspaceSelector.tsx', '/src/pages/AccountPage.tsx',
    '/src/pages/suppliers/SupplierListPage.tsx', '/src/pages/purchase-orders/PurchaseOrderListPage.tsx',
    '/src/pages/deliveries/DeliveryListPage.tsx', '/src/pages/invoices/InvoiceListPage.tsx',
  ].map(async (path) => (await server.ssrLoadModule(path)).default))
  originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { location: { hash: '#/suppliers' } } })
})
after(async () => {
  if (server) await server.close()
  if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow)
  else delete globalThis.window
})
function markup(component, role, props = {}, memberships = [membership(workspaceId, role)]) {
  const state = { status: 'ready', message: '', warning: null, version: 1, me: me(memberships), selected: memberships[0] ?? null }
  const session = { snapshot: () => state, subscribe: () => () => {} }
  return renderToStaticMarkup(createElement(context, { value: session }, createElement(component, props)))
}
test('Vite binds loopback and serves canonical localhost plus the query callback SPA', async () => {
  const address = server.httpServer.address()
  assert.ok(['127.0.0.1', '::1'].includes(address.address))
  const base = `http://localhost:${address.port}`
  for (const path of ['/', '/auth/callback?code=synthetic-code&state=synthetic-state']) {
    const response = await fetch(base + path)
    assert.equal(response.status, 200)
    assert.match(await response.text(), /src\/main.tsx/)
  }
})
test('actual read pages hide create links for approvers and show them to creating roles', () => {
  for (const component of components.slice(3)) {
    for (const role of ['administrator', 'accountant']) assert.match(markup(component, role, { page: { limit: 20, offset: 0 } }), /href="#\/(suppliers|purchase-orders|deliveries|invoices)\/new"/)
    assert.doesNotMatch(markup(component, 'approver', { page: { limit: 20, offset: 0 } }), /href="#\/(suppliers|purchase-orders|deliveries|invoices)\/new"/)
  }
})
test('navigation and account expose member management only to administrators', () => {
  for (const component of [components[0], components[2]]) {
    assert.match(markup(component, 'administrator', { route: { kind: 'status' } }), /href="#\/memberships"/)
    for (const role of ['accountant', 'approver']) assert.doesNotMatch(markup(component, role, { route: { kind: 'status' } }), /href="#\/memberships"/)
  }
})
test('rendered onboarding shows own application ID and explicit creation without demo access', () => {
  const html = markup(components[2], undefined, {}, [])
  assert.match(html, /50000000-0000-4000-8000-000000000011/)
  assert.match(html, /no workspace memberships/)
  assert.match(html, /Signing in does not grant local-demo access/)
  assert.match(html, /href="#\/workspaces\/new"/)
})
test('workspace selector uses only accessible memberships and displays current role', () => {
  const html = markup(components[1], 'approver')
  assert.match(html, /Current role: <strong>approver/)
  assert.match(html, new RegExp(workspaceId))
  assert.doesNotMatch(html, /00000000-0000-4000-8000-000000000001/)
})
