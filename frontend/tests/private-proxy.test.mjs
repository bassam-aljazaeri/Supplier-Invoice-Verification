import assert from 'node:assert/strict'
import { createServer as httpServer } from 'node:http'
import { once } from 'node:events'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createLogger, createServer, loadConfigFromFile } from 'vite'
import { privateProxyLogger } from '../src/privateProxyLogger.ts'

test('real local proxy failure never logs download ticket, bearer, raw exception or response bytes', async (t) => {
  // The upstream is this disposable loopback fixture, never the development API.
  const upstream = httpServer((request) => request.socket.destroy())
  upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening')
  let server
  t.after(async () => { if (server) await server.close(); await new Promise((resolve) => upstream.close(resolve)) })
  const logs = [], root = fileURLToPath(new URL('../', import.meta.url))
  const loaded = await loadConfigFromFile({ command: 'serve', mode: 'test' }, root + 'vite.config.ts')
  assert.ok(loaded.config.customLogger)
  const logger = privateProxyLogger({ ...createLogger('silent'), error: (message, options) => logs.push({ message, options }) })
  server = await createServer({ ...loaded.config, root, configFile: false, envDir: false, customLogger: logger,
    server: { ...loaded.config.server, port: 0, hmr: false, proxy: { '/api': { ...loaded.config.server.proxy['/api'], target: `http://127.0.0.1:${upstream.address().port}` } } } })
  await server.listen()
  const response = await fetch(`http://localhost:${server.httpServer.address().port}/api/documents/80000000-0000-4000-8000-000000000011/local-content?ticket=FICTIONAL-DO-NOT-LOG`, {
    headers: { Authorization: 'Bearer FICTIONAL-ACCESS-TOKEN', 'X-Workspace-ID': '00000000-0000-4000-8000-000000000011' },
  })
  assert.equal(response.status, 502); await response.text()
  assert.equal(logs.length, 1)
  assert.equal(logs[0].message, 'Local API proxy request failed; private request details withheld.')
  assert.doesNotMatch(JSON.stringify(logs), /FICTIONAL|ticket|Bearer|stack|socket hang up/)
})

test('proxy logging drops raw Error options and keeps unrelated build diagnostics', () => {
  const logs = []
  const logger = privateProxyLogger({ ...createLogger('silent'), error: (message, options) => logs.push([message, options]) })
  logger.error('http proxy error: /private?ticket=FICTIONAL', { error: new Error('FICTIONAL-SECRET'), timestamp: true })
  assert.doesNotMatch(JSON.stringify(logs), /FICTIONAL|ticket|stack/)
  logger.error('TypeScript source compilation failed.', { timestamp: false })
  assert.equal(logs[1][0], 'TypeScript source compilation failed.')
})
