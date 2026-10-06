export type CheckState = 'loading' | 'ok' | 'unavailable' | 'failed' | 'timed_out'

export type DependencySnapshot = {
  database: CheckState
  redis: CheckState
}

export type StatusSnapshot = DependencySnapshot & { api: CheckState }

type RequestOptions = {
  signal?: AbortSignal
  timeoutMs?: number
}

export const initialStatus: StatusSnapshot = {
  api: 'loading',
  database: 'loading',
  redis: 'loading',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function dependencyState(value: unknown): CheckState {
  if (value === 'ok') return 'ok'
  if (value === 'unavailable') return 'unavailable'
  return 'failed'
}

function failureState(error: unknown): CheckState {
  return error instanceof DOMException && error.name === 'TimeoutError'
    ? 'timed_out'
    : 'failed'
}

async function requestJson(path: string, options: RequestOptions) {
  const controller = new AbortController()
  const timeoutId = setTimeout(
    () => controller.abort(new DOMException('Request timed out', 'TimeoutError')),
    options.timeoutMs ?? 5000,
  )
  const signal = options.signal
    ? AbortSignal.any([controller.signal, options.signal])
    : controller.signal

  try {
    const response = await fetch(path, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal,
    })
    // Keep the timeout active until the entire JSON body has been read.
    const body: unknown = await response.json()
    return { response, body }
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function getHealthStatus(options: RequestOptions = {}): Promise<CheckState> {
  try {
    const { response, body } = await requestJson('/api/health', options)
    if (!response.ok) return 'unavailable'
    return isRecord(body) && body.status === 'ok' ? 'ok' : 'failed'
  } catch (error) {
    return failureState(error)
  }
}

export async function getReadinessStatus(
  options: RequestOptions = {},
): Promise<DependencySnapshot> {
  try {
    const { response, body } = await requestJson('/api/ready', options)
    // FastAPI uses HTTP 503 to report dependency failures, with useful JSON.
    if ((!response.ok && response.status !== 503) || !isRecord(body)) {
      return { database: 'failed', redis: 'failed' }
    }
    return {
      database: dependencyState(body.database),
      redis: dependencyState(body.redis),
    }
  } catch (error) {
    const state = failureState(error)
    return { database: state, redis: state }
  }
}
