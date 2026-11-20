import type { Logger } from 'vite'

// Vite's proxy error includes the full request URL and Error object. Local-content
// URLs contain tickets; neither may reach the terminal when the backend is down.
export function privateProxyLogger(base: Logger): Logger {
  return {
    ...base,
    get hasWarned() { return base.hasWarned },
    error(message, options) {
      if (message.includes('proxy error:')) base.error('Local API proxy request failed; private request details withheld.', { timestamp: options?.timestamp })
      else base.error(message, options)
    },
  }
}
