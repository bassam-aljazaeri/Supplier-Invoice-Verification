// Guard completion as well as cancelling transport: obsolete promises may still settle.
export function createRequestScope() {
  let current: AbortController | null = null
  return {
    start() {
      current?.abort()
      current = new AbortController()
      return current
    },
    isCurrent(controller: AbortController) {
      return current === controller && !controller.signal.aborted
    },
    cancel() {
      current?.abort()
      current = null
    },
  }
}
