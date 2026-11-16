import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ApiFailure } from '../src/api.ts'
import { createUploadFlow } from '../src/documentUpload.ts'
import { createDocumentPoller } from '../src/documentPolling.ts'
import { attemptKey, documentRecord, fictionalFile } from './document-fixtures.mjs'
import { deferred, flush } from './auth-fixtures.mjs'

test('same-attempt replay requires lookup, waits the request window and retains exactly the original file/key', async () => {
  let now = 0, count = 0, keys = 0
  const sent = [], file = fictionalFile()
  const flow = createUploadFlow({ version: () => 1, now: () => now, uuid: () => { keys++; return attemptKey },
    upload: async (file, key) => { sent.push([file, key]); if (++count === 1) throw new ApiFailure('network', 'Synthetic lost response', [], undefined, true); return documentRecord() },
    recover: async () => ({ items: [], limit: 20, offset: 0, total: 0 }) })
  flow.activate(); flow.select(file)
  await flow.submit(); assert.equal(flow.snapshot().uncertain, true)
  await flow.submit(); assert.equal(count, 1)
  await flow.recover(); await flow.submit(); assert.equal(count, 1)
  now = 90001; await flow.submit()
  assert.equal(count, 2); assert.equal(keys, 1)
  assert.deepEqual(sent, [[file, attemptKey], [file, attemptKey]])
  assert.equal(flow.snapshot().file, null)
  flow.dispose()
})

test('double submit is blocked before render and recovery finds the durable record without writing again', async () => {
  const waiting = deferred(); let calls = 0
  const flow = createUploadFlow({ version: () => 1, now: () => 0, uuid: () => attemptKey,
    upload: async () => { calls++; return waiting.promise }, recover: async () => ({ items: [documentRecord()], total: 1, limit: 20, offset: 0 }) })
  flow.activate(); flow.select(fictionalFile())
  const pending = flow.submit(); await flow.submit(); assert.equal(calls, 1)
  waiting.reject(new ApiFailure('timeout', 'Synthetic', [], undefined, true)); await pending
  await flow.recover(); assert.equal(calls, 1); assert.equal(flow.snapshot().document.id, documentRecord().id)
  assert.equal(flow.snapshot().file, null)
})

test('new selection gets a new key and leaving upload flow releases files and ignores late results', async () => {
  let version = 1, keys = 0, saved = 0, signal
  const response = deferred()
  const flow = createUploadFlow({ version: () => version, now: () => 0, uuid: () => String(++keys),
    upload: async (_, __, options) => { signal = options.signal; return response.promise }, recover: async () => { throw new Error('Unused') } })
  flow.activate(); flow.select(fictionalFile()); flow.reset(); flow.select(fictionalFile()); assert.equal(keys, 2)
  const pending = flow.submit(() => saved++)
  version++; flow.dispose()
  assert.equal(signal.aborted, true); assert.equal(flow.snapshot().file, null); assert.equal(flow.snapshot().key, null)
  response.resolve(documentRecord()); await pending; assert.equal(saved, 0)
  assert.equal(flow.snapshot().document, null)
})

test('an idle file selection cannot be sent or exposed after a workspace/session change', async () => {
  let version = 1, writes = 0
  const flow = createUploadFlow({ version: () => version, now: () => 0, uuid: () => attemptKey,
    upload: async () => { writes++; return documentRecord() }, recover: async () => { throw new Error('Unused') } })
  flow.activate(); flow.select(fictionalFile()); version++
  assert.equal(flow.snapshot().file, null)
  await flow.submit(); assert.equal(writes, 0); assert.equal(flow.snapshot().key, null)
})

function clock() {
  let time = 0, id = 0
  const jobs = new Map()
  return { now: () => time, later(fn, delay) { const key = ++id; jobs.set(key, { fn, at: time + delay }); return () => jobs.delete(key) },
    async advance(ms) {
      const end = time + ms
      while (true) {
        const [key, value] = [...jobs.entries()].filter(([, job]) => job.at <= end).sort((a, b) => a[1].at - b[1].at)[0] ?? []
        if (!value) break
        time = value.at; jobs.delete(key); value.fn(); await flush()
      }
      time = end; await flush()
    }, size: () => jobs.size }
}

test('polling never overlaps a read, stops at terminal state and releases all timers', async () => {
  const time = clock(), first = deferred(); let reads = 0
  const poller = createDocumentPoller(async () => { reads++; return reads === 1 ? first.promise : documentRecord({ state: 'accepted', detected_type: 'pdf' }) }, { ...time, version: () => 1 })
  poller.start(); poller.refresh(); await time.advance(10000); assert.equal(reads, 1)
  first.resolve(documentRecord()); await flush(); await time.advance(2999); assert.equal(reads, 1)
  await time.advance(1); assert.equal(reads, 2); assert.equal(poller.snapshot().reason, 'terminal'); assert.equal(time.size(), 0)
  await time.advance(60000); assert.equal(reads, 2)
})

test('poll cadence changes after five reads and caps automatic reads at twenty', async () => {
  const time = clock(); const at = []
  const poller = createDocumentPoller(async () => { at.push(time.now()); return documentRecord() }, { ...time, version: () => 1 })
  poller.start(); await flush(); await time.advance(120000)
  assert.deepEqual(at.slice(0, 7), [0, 3000, 6000, 9000, 12000, 17000, 22000])
  assert.equal(at.length, 20); assert.equal(poller.snapshot().reason, 'limit'); assert.equal(time.size(), 0)
  poller.refresh(); await flush(); assert.equal(at.length, 21)
  await time.advance(120000); assert.equal(at.length, 21)
})

test('hidden tab cancels in-flight status reads; only explicit refresh can resume', async () => {
  const time = clock(), response = deferred(); let reads = 0, signal
  const poller = createDocumentPoller(async (incoming) => { signal = incoming; reads++; return response.promise }, { ...time, version: () => 1 })
  poller.start(); poller.pause(); assert.equal(signal.aborted, true)
  response.resolve(documentRecord()); await flush(); await time.advance(20000)
  assert.equal(reads, 1); assert.equal(poller.snapshot().data, null)
  poller.refresh(); await flush(); assert.equal(reads, 2)
  poller.dispose(); assert.equal(time.size(), 0)
})

test('navigation/logout/workspace generation change blocks obsolete status and cancels scheduling', async () => {
  const time = clock(), response = deferred(); let version = 1, signal
  const poller = createDocumentPoller(async (incoming) => { signal = incoming; return response.promise }, { ...time, version: () => version })
  poller.start(); version++; response.resolve(documentRecord()); await flush()
  assert.equal(signal.aborted, true); assert.equal(poller.snapshot().data, null); assert.equal(time.size(), 0)
})

test('a slow read is aborted at two minutes and errors stop polling until user refresh', async () => {
  const time = clock(), pending = deferred(); let signal
  const poller = createDocumentPoller(async (incoming) => { signal = incoming; return pending.promise }, { ...time, version: () => 1 })
  poller.start(); await time.advance(120000); assert.equal(signal.aborted, true); assert.equal(poller.snapshot().reason, 'limit')
  pending.resolve(documentRecord()); await flush(); assert.equal(poller.snapshot().data, null)
  let calls = 0
  const errors = createDocumentPoller(async () => { calls++; throw new ApiFailure('network', 'Synthetic error') }, { ...time, version: () => 1 })
  errors.start(); await flush(); await time.advance(120000); assert.equal(calls, 1); assert.equal(errors.snapshot().reason, 'error')
  errors.refresh(); await flush(); assert.equal(calls, 2)
  errors.dispose()
})

test('effect cleanup/restart (Strict Mode) cannot let an earlier read replace a newer one', async () => {
  const time = clock(), old = deferred(); let calls = 0
  const poller = createDocumentPoller(async () => ++calls === 1 ? old.promise : documentRecord({ state: 'accepted', detected_type: 'png' }), { ...time, version: () => 1 })
  poller.start(); poller.dispose(); poller.start(); await flush()
  old.resolve(documentRecord()); await flush()
  assert.equal(poller.snapshot().data.state, 'accepted'); assert.equal(time.size(), 0)
})

test('returning from a hidden tab cannot extend the original two-minute automatic budget', async () => {
  const time = clock(), slow = deferred(); let calls = 0, signal
  const poller = createDocumentPoller(async (incoming) => { signal = incoming; return ++calls === 1 ? documentRecord() : slow.promise }, { ...time, version: () => 1 })
  poller.start(); await flush(); poller.pause(); await time.advance(119000)
  poller.refresh(); await flush(); await time.advance(1000)
  assert.equal(signal.aborted, true); assert.equal(poller.snapshot().reason, 'limit')
  slow.resolve(documentRecord()); await flush(); assert.equal(calls, 2); assert.equal(time.size(), 0)
})
