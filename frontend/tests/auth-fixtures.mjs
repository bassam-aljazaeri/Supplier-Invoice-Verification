import { InMemoryWebStorage } from 'oidc-client-ts'
import { readAuthConfig } from '../src/authConfig.ts'
import { BrowserSession } from '../src/session.ts'

export const publicSettings = {
  VITE_COGNITO_AUTHORITY: 'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_SYNTHETIC',
  VITE_COGNITO_CLIENT_ID: 'syntheticclient',
  VITE_COGNITO_DOMAIN: 'https://synthetic.auth.eu-west-1.amazoncognito.com',
  VITE_AUTH_CALLBACK_URL: 'http://localhost:5173/auth/callback',
  VITE_AUTH_LOGOUT_URL: 'http://localhost:5173/',
}
export const configuration = readAuthConfig(publicSettings)
export const workspaceId = '00000000-0000-4000-8000-000000000011'
export const otherWorkspaceId = '00000000-0000-4000-8000-000000000012'
export const userId = '50000000-0000-4000-8000-000000000011'
export const timestamp = '2026-10-17T09:00:00Z'
export const identity = () => ({ issuer: configuration.config.authority, subject: 'synthetic-subject', expiresAt: Date.now() / 1000 + 900, returnHash: '#/account' })
export const membership = (workspace = workspaceId, role = 'administrator') => ({
  id: workspace.replace('00000000-', '60000000-'), workspace_id: workspace, application_user_id: userId, role,
  created_at: timestamp, updated_at: timestamp,
  workspace: { id: workspace, slug: workspace === workspaceId ? 'synthetic-one' : 'synthetic-two', name: 'Synthetic workspace', created_at: timestamp },
})
export const me = (memberships = [membership()]) => ({ user: { id: userId, issuer: configuration.config.authority, subject: 'synthetic-subject', created_at: timestamp, updated_at: timestamp }, memberships })
export const supplier = (workspace = workspaceId) => ({ id: '10000000-0000-4000-8000-000000000011', workspace_id: workspace, created_at: timestamp, supplier_code: 'SYNTHETIC', name: 'Synthetic supplier', notes: null })
export const page = (items) => ({ items, limit: 20, offset: 0, total: items.length })
export const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
export const flush = () => new Promise((resolve) => setImmediate(resolve))

export function harness(t, options = {}) {
  const events = [], storage = new InMemoryWebStorage()
  const signed = identity()
  const client = {
    signIn: async () => configuration.config.domain + '/oauth2/authorize?synthetic=1',
    callback: async () => signed,
    renew: async () => identity(),
    accessToken: () => 'synthetic-access-token',
    clear: () => { events.push('clear-user') },
    takeRevocation: () => async () => { events.push('revoke-refresh') },
    ...options.client,
  }
  const host = {
    origin: () => 'http://localhost:5173',
    replace: (hash) => events.push(['replace', hash]),
    external: (url) => events.push(['external', url]),
    clearCallback: () => events.push('strip-query'),
    clearTransient: () => { storage.clear(); events.push('clear-state') },
    ...options.host,
  }
  const session = new BrowserSession(options.configuration ?? configuration, () => client, host, options.loadMe ?? (async () => me()), options.deadline ?? 10000)
  t.after(() => session.end())
  return { session, client, events, host, signed, storage, start: () => session.start(configuration.config.callbackUrl + '?code=synthetic&state=synthetic') }
}
