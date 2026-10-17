import { readAuthConfig } from './authConfig.ts'
import { clearLoginState, createAuthClient } from './auth.ts'
import { BrowserSession } from './session.ts'

const configuration = readAuthConfig({
  VITE_COGNITO_AUTHORITY: import.meta.env.VITE_COGNITO_AUTHORITY,
  VITE_COGNITO_CLIENT_ID: import.meta.env.VITE_COGNITO_CLIENT_ID,
  VITE_COGNITO_DOMAIN: import.meta.env.VITE_COGNITO_DOMAIN,
  VITE_AUTH_CALLBACK_URL: import.meta.env.VITE_AUTH_CALLBACK_URL,
  VITE_AUTH_LOGOUT_URL: import.meta.env.VITE_AUTH_LOGOUT_URL,
})
export const session = new BrowserSession(configuration, () => {
  if (!configuration.config) throw new Error('Configure authentication first.')
  return createAuthClient(configuration.config, window.sessionStorage)
}, {
  origin: () => window.location.origin,
  clearCallback: () => window.history.replaceState(null, '', '/#/account'),
  clearTransient: () => clearLoginState(window.sessionStorage),
  replace: (hash) => {
    window.history.replaceState(null, '', '/' + hash)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  },
  external: (url) => window.location.assign(url),
})

let started = false
const restored = (event: PageTransitionEvent) => { if (event.persisted) session.cancelPending() }
export function startBrowserSession() {
  if (started) return
  started = true
  // Called outside React. StrictMode cannot trigger a second code exchange.
  void session.start(window.location.href)
  window.addEventListener('hashchange', session.cancelPending)
  window.addEventListener('pageshow', restored)
}

if (import.meta.hot) import.meta.hot.dispose(() => {
  session.end()
  window.removeEventListener('hashchange', session.cancelPending)
  window.removeEventListener('pageshow', restored)
})
