import { useCallback, useEffect, useRef, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ApiFailure, privateContextVersion } from '../api.ts'
import { subscribeHashChange } from '../navigation.ts'
import { createRequestScope } from '../requestScope.ts'

export type SaveFeedback = { pending: boolean; error: ApiFailure | null }
type ReadResult<T> = { key: string; attempt: number; data: T | null; error: ApiFailure | null }

export function useRead<T>(inputKey: string, load: (signal: AbortSignal) => Promise<T>) {
  const key = `${privateContextVersion()}:${inputKey}`
  const [attempt, setAttempt] = useState(0)
  const [pageHash] = useState(() => window.location.hash)
  const [result, setResult] = useState<ReadResult<T> | null>(null)
  useEffect(() => {
    const scope = createRequestScope(privateContextVersion)
    const controller = scope.start()
    const unsubscribe = subscribeHashChange(() => scope.cancel())
    const current = () => scope.isCurrent(controller) && window.location.hash === pageHash
    void load(controller.signal).then((data) => {
      if (current()) setResult({ key, attempt, data, error: null })
    }).catch((error: unknown) => {
      if (current()) setResult({ key, attempt, data: null, error: error instanceof ApiFailure ? error : new ApiFailure('server', 'The request could not be completed.') })
    })
    return () => { scope.cancel(); unsubscribe() }
  }, [key, load, attempt, pageHash])
  const ready = result?.key === key && result.attempt === attempt
  return { loading: !ready, data: ready ? result.data : null, error: ready ? result.error : null, retry: () => setAttempt((value) => value + 1) }
}

export function useSave(setFeedback: Dispatch<SetStateAction<SaveFeedback>>) {
  const active = useRef<AbortController | null>(null)
  const scope = useRef(createRequestScope(privateContextVersion))
  const [pageHash] = useState(() => window.location.hash)
  useEffect(() => {
    const gate = scope.current
    const cancel = () => {
      if (active.current) {
        gate.cancel()
        active.current = null
        setFeedback({ pending: false, error: new ApiFailure('cancelled', 'The save was interrupted.', [], undefined, true) })
      }
    }
    const unsubscribe = subscribeHashChange(cancel)
    return () => { cancel(); unsubscribe() }
  }, [setFeedback])
  return useCallback(async <T,>(save: (signal: AbortSignal) => Promise<T>, onSaved: (value: T) => void) => {
    // Block repeat submits before React has rendered the disabled button.
    if (active.current) return
    const controller = scope.current.start()
    active.current = controller
    setFeedback({ pending: true, error: null })
    try {
      const saved = await save(controller.signal)
      if (scope.current.isCurrent(controller) && window.location.hash === pageHash) {
        active.current = null
        setFeedback({ pending: false, error: null })
        onSaved(saved)
      }
    } catch (error) {
      if (scope.current.isCurrent(controller) && window.location.hash === pageHash) {
        active.current = null
        setFeedback({ pending: false, error: error instanceof ApiFailure ? error : new ApiFailure('server', 'The save could not be completed.', [], undefined, true) })
      }
    }
  }, [pageHash, setFeedback])
}
