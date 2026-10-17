// Guard completion as well as cancelling transport: obsolete promises may still settle.
export function createRequestScope(context = () => 0) {
  let current: AbortController | null = null
  let generation = context()
  return {
    start() {
      current?.abort()
      current = new AbortController()
      generation = context()
      return current
    },
    isCurrent(controller: AbortController) {
      return current === controller && !controller.signal.aborted && generation === context()
    },
    cancel() {
      current?.abort()
      current = null
    },
  }
}
