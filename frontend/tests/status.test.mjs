import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getHealthStatus, getReadinessStatus } from '../src/status.ts'

const healthyDependencies = { status: 'ready', database: 'ok', redis: 'ok' }
const failedDependencies = { database: 'failed', redis: 'failed' }

function json(body, status = 200) {
  return Response.json(body, { status })
}

function waitForAbort(signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason)
    } else {
      signal.addEventListener('abort', () => reject(signal.reason), { once: true })
    }
  })
}

test('checks health through the frontend proxy path without cached results', async (t) => {
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.equal(path, '/api/health')
    assert.equal(options.headers.Accept, 'application/json')
    assert.equal(options.cache, 'no-store')
    assert.ok(options.signal instanceof AbortSignal)
    return json({ status: 'ok' })
  })
  assert.equal(await getHealthStatus(), 'ok')
})

test('checks each dependency through the readiness proxy path', async (t) => {
  t.mock.method(globalThis, 'fetch', async (path) => {
    assert.equal(path, '/api/ready')
    return json(healthyDependencies)
  })
  assert.deepEqual(await getReadinessStatus(), { database: 'ok', redis: 'ok' })
})

for (const unavailable of ['database', 'redis']) {
  test(`preserves both dependency results on HTTP 503 when ${unavailable} is down`, async (t) => {
    const body = { ...healthyDependencies, status: 'not_ready', [unavailable]: 'unavailable' }
    t.mock.method(globalThis, 'fetch', async () => json(body, 503))
    assert.deepEqual(await getReadinessStatus(), {
      database: 'ok', redis: 'ok', [unavailable]: 'unavailable',
    })
  })
}

test('reports both dependencies unavailable on HTTP 503', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => json({
    status: 'not_ready', database: 'unavailable', redis: 'unavailable',
  }, 503))
  assert.deepEqual(await getReadinessStatus(), {
    database: 'unavailable', redis: 'unavailable',
  })
})

test('an HTTP error cannot produce healthy API or readiness results', async (t) => {
  t.mock.method(globalThis, 'fetch', async (path) => json(
    path === '/api/health' ? { status: 'ok' } : healthyDependencies,
    500,
  ))
  assert.equal(await getHealthStatus(), 'unavailable')
  assert.deepEqual(await getReadinessStatus(), failedDependencies)
})

test('reports network failures and succeeds on the next refresh', async (t) => {
  let available = false
  t.mock.method(globalThis, 'fetch', async (path) => {
    if (!available) throw new TypeError('Failed to fetch')
    return json(path === '/api/health' ? { status: 'ok' } : healthyDependencies)
  })
  assert.equal(await getHealthStatus(), 'failed')
  assert.deepEqual(await getReadinessStatus(), failedDependencies)
  available = true
  assert.equal(await getHealthStatus(), 'ok')
  assert.deepEqual(await getReadinessStatus(), { database: 'ok', redis: 'ok' })
})

test('a readiness failure leaves API health independent and can recover', async (t) => {
  let ready = false
  t.mock.method(globalThis, 'fetch', async (path) => {
    if (path === '/api/health') return json({ status: 'ok' })
    return ready
      ? json(healthyDependencies)
      : json({ status: 'not_ready', database: 'unavailable', redis: 'ok' }, 503)
  })
  const [health, dependencies] = await Promise.all([getHealthStatus(), getReadinessStatus()])
  assert.equal(health, 'ok')
  assert.deepEqual(dependencies, { database: 'unavailable', redis: 'ok' })
  ready = true
  assert.deepEqual(await getReadinessStatus(), { database: 'ok', redis: 'ok' })
})

test('does not accept malformed JSON, including an HTTP 503 HTML error', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>Proxy error</html>', {
    status: 503, headers: { 'Content-Type': 'text/html' },
  }))
  assert.equal(await getHealthStatus(), 'failed')
  assert.deepEqual(await getReadinessStatus(), failedDependencies)
})

for (const body of [null, [], 'ok', {}]) {
  test(`does not mark unexpected JSON ${JSON.stringify(body)} as healthy`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => json(body))
    assert.equal(await getHealthStatus(), 'failed')
    assert.deepEqual(await getReadinessStatus(), failedDependencies)
  })
}

test('keeps valid dependency results when another field is missing or invalid', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => json({ database: 'ok', redis: 'unknown' }, 503))
  assert.deepEqual(await getReadinessStatus(), { database: 'ok', redis: 'failed' })
})

test('times out a request that never returns headers', { timeout: 1000 }, async (t) => {
  t.mock.method(globalThis, 'fetch', (path, { signal }) => waitForAbort(signal))
  assert.equal(await getHealthStatus({ timeoutMs: 15 }), 'timed_out')
  assert.deepEqual(await getReadinessStatus({ timeoutMs: 15 }), {
    database: 'timed_out', redis: 'timed_out',
  })
})

test('timeout remains active while reading JSON, then a later request recovers', { timeout: 1000 }, async (t) => {
  let stalled = true
  let bodyStarted = false
  t.mock.method(globalThis, 'fetch', async (path, { signal }) => {
    if (!stalled) return json(healthyDependencies)
    return {
      ok: true,
      status: 200,
      json: () => {
        bodyStarted = true
        return waitForAbort(signal)
      },
    }
  })
  assert.deepEqual(await getReadinessStatus({ timeoutMs: 15 }), {
    database: 'timed_out', redis: 'timed_out',
  })
  assert.equal(bodyStarted, true)
  stalled = false
  assert.deepEqual(await getReadinessStatus(), { database: 'ok', redis: 'ok' })
})

test('cancels outstanding requests when the page releases its controller', async (t) => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', (path, { signal }) => waitForAbort(signal))
  const health = getHealthStatus({ signal: controller.signal })
  const readiness = getReadinessStatus({ signal: controller.signal })
  controller.abort()
  assert.equal(await health, 'failed')
  assert.deepEqual(await readiness, failedDependencies)
})
