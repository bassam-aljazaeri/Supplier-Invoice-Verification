import { ApiFailure, privateContextVersion } from './api.ts'
import type { DocumentRecord } from './documentTypes.ts'
import { activeDocument } from './documentTypes.ts'
import { createRequestScope } from './requestScope.ts'

export type PollSnapshot = { data: DocumentRecord | null; error: ApiFailure | null; busy: boolean; reason: 'terminal' | 'limit' | 'hidden' | 'error' | null; revision: number }
const empty: PollSnapshot = { data: null, error: null, busy: false, reason: null, revision: 0 }
const later = (callback: () => void, delay: number) => { const timer = setTimeout(callback, delay); return () => clearTimeout(timer) }

export function createDocumentPoller(load: (signal: AbortSignal) => Promise<DocumentRecord>, deps = { version: privateContextVersion, now: () => performance.now(), later }) {
  let state = empty, live = false, owner = deps.version(), reads = 0, started = 0
  let active: AbortController | null = null
  let cancelNext = () => {}, cancelDeadline = () => {}
  const listeners = new Set<() => void>(), scope = createRequestScope(deps.version)
  const emit = (next: PollSnapshot) => { state = next; listeners.forEach((listener) => listener()) }
  const dispose = () => { live = false; scope.cancel(); active = null; cancelNext(); cancelDeadline(); emit(empty) }
  const valid = () => {
    if (owner !== deps.version()) dispose()
    return live
  }
  const pause = (reason: 'hidden' | 'limit') => {
    cancelNext(); cancelDeadline(); scope.cancel()
    emit({ ...state, busy: false, reason })
  }
  async function read() {
    if (!valid() || active) return
    cancelNext()
    cancelDeadline()
    const remaining = 120000 - (deps.now() - started)
    if (remaining > 0 && reads < 20) cancelDeadline = deps.later(() => pause('limit'), remaining)
    const controller = scope.start()
    active = controller
    reads++
    emit({ ...state, busy: true, error: null })
    try {
      const data = await load(controller.signal)
      if (!valid() || !scope.isCurrent(controller)) return
      const reason = !activeDocument(data) ? 'terminal' : reads >= 20 || deps.now() - started >= 120000 ? 'limit' : null
      emit({ data, error: null, busy: false, reason, revision: state.revision + 1 })
      if (reason) cancelDeadline()
      else cancelNext = deps.later(() => { void read() }, reads < 5 ? 3000 : 5000)
    } catch (error) {
      if (valid() && scope.isCurrent(controller)) {
        cancelDeadline()
        emit({ ...state, busy: false, reason: 'error', error: error instanceof ApiFailure ? error : new ApiFailure('server', 'The document status could not be read.') })
      }
    } finally {
      if (active === controller) active = null
    }
  }
  return {
    snapshot: () => owner === deps.version() ? state : empty,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } },
    start(visible = true) {
      owner = deps.version(); live = true; reads = 0; started = deps.now()
      if (!visible) { pause('hidden'); return }
      cancelDeadline = deps.later(() => pause('limit'), 120000)
      void read()
    },
    pause: () => { if (valid()) pause('hidden') }, dispose,
    refresh: () => { if (valid()) void read() },
  }
}
