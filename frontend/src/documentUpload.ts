import { ApiFailure, privateContextVersion } from './api.ts'
import { getDocuments, uploadDocument, validateDocumentFile } from './documentApi.ts'
import type { DocumentRecord } from './documentTypes.ts'
import { createRequestScope } from './requestScope.ts'

export type UploadSnapshot = {
  file: File | null; key: string | null; pending: boolean; uncertain: boolean
  error: ApiFailure | null; recovery: 'absent' | null; replayAfter: number; document: DocumentRecord | null
}
const empty: UploadSnapshot = { file: null, key: null, pending: false, uncertain: false, error: null, recovery: null, replayAfter: 0, document: null }

export function createUploadFlow(deps = { upload: uploadDocument, recover: getDocuments, version: privateContextVersion, now: Date.now, uuid: () => crypto.randomUUID() }) {
  let state = empty, live = false, owner = deps.version()
  let active: AbortController | null = null
  const listeners = new Set<() => void>()
  const scope = createRequestScope(deps.version)
  const emit = (next: UploadSnapshot) => { state = next; listeners.forEach((listener) => listener()) }
  const dispose = () => { live = false; scope.cancel(); active = null; emit(empty) }
  const current = () => {
    if (owner !== deps.version()) dispose()
    return live
  }
  const canReplay = () => state.uncertain && state.recovery === 'absent' && deps.now() >= state.replayAfter
  async function run(recover: boolean, saved?: (document: DocumentRecord) => void) {
    if (!current() || active || !state.file || !state.key || (!recover && state.uncertain && !canReplay())) return
    const { file, key } = state
    const controller = scope.start()
    active = controller
    emit({ ...state, pending: true, error: null })
    try {
      const result = recover ? await deps.recover({ limit: 20, offset: 0 }, { signal: controller.signal }, key) : await deps.upload(file, key, { signal: controller.signal })
      if (!current() || !scope.isCurrent(controller)) return
      const document = 'items' in result ? result.items[0] : result
      if ('items' in result && (result.items.length > 1 || result.total !== result.items.length)) throw new ApiFailure('invalid-response', 'The upload status could not be read.')
      active = null
      if (document) {
        emit({ ...empty, document })  // Release bytes once the durable record is known.
        if (current() && scope.isCurrent(controller)) saved?.(document)
      } else emit({ ...state, pending: false, recovery: 'absent' })
      return document
    } catch (error) {
      if (!current() || !scope.isCurrent(controller)) return
      active = null
      const failure = error instanceof ApiFailure ? error : new ApiFailure('server', 'The upload could not be confirmed.', [], undefined, !recover)
      const uncertain = state.uncertain || failure.uncertainWrite
      emit({ ...state, pending: false, error: failure, uncertain,
        recovery: !recover ? null : state.recovery,
        // An empty lookup cannot exclude a late reservation. Wait a full server
        // request window after an uncertain write; only a user can resend it.
        replayAfter: !recover && failure.uncertainWrite ? deps.now() + 90000 : state.replayAfter })
    }
  }
  return {
    snapshot: () => owner === deps.version() ? state : empty,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } },
    activate: () => { owner = deps.version(); live = true }, dispose,
    select(file: File | null) {
      if (!current() || active) return
      const message = validateDocumentFile(file)
      emit(message ? { ...empty, error: new ApiFailure('validation', message, [{ field: 'file', message }]) }
        : { ...empty, file, key: deps.uuid() })
    },
    reset() { if (current() && !active) emit(empty) },
    canReplay,
    submit: (saved?: (document: DocumentRecord) => void) => run(false, saved),
    recover: (saved?: (document: DocumentRecord) => void) => run(true, saved),
  }
}
