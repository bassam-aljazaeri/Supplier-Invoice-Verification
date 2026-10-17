import { ApiFailure, configurePrivateRequests } from './api.ts'
import { getMe } from './accountApi.ts'
import { bounded, cognitoLogoutUrl } from './auth.ts'
import type { AuthClient, BrowserIdentity } from './auth.ts'
import type { AuthConfiguration } from './authConfig.ts'
import type { Me, OwnMembership } from './authTypes.ts'
import { safeReturnHash } from './navigation.ts'

export type SessionSnapshot = {
  status: 'setup' | 'signed-out' | 'signing-in' | 'callback' | 'loading' | 'ready' | 'access-error' | 'logging-out'
  message: string; me: Me | null; selected: OwnMembership | null; version: number; warning: string | null
}
export type SessionHost = {
  origin: () => string
  replace: (hash: string) => void
  external: (url: string) => void
  clearCallback: () => void
  clearTransient: () => void
}

export class BrowserSession {
  private state: SessionSnapshot
  private listeners = new Set<() => void>()
  private configuration: AuthConfiguration
  private host: SessionHost
  private factory: () => AuthClient
  private loadMe: typeof getMe
  private client: AuthClient | null = null
  private identity: BrowserIdentity | null = null
  private generation = 0
  private timer: ReturnType<typeof setTimeout> | undefined
  private renewal: Promise<string> | null = null
  private refreshing: Promise<void> | null = null
  private startup: Promise<void> | null = null
  private callbackActive = false
  private deadline: number

  constructor(configuration: AuthConfiguration, factory: () => AuthClient, host: SessionHost, loadMe = getMe, deadline = 10000) {
    this.configuration = configuration
    this.factory = factory
    this.host = host
    this.loadMe = loadMe
    this.deadline = deadline
    this.state = { status: configuration.config ? 'signed-out' : 'setup', message: configuration.error ?? '', me: null, selected: null, version: 0, warning: null }
  }
  snapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private publish(next: Partial<SessionSnapshot>) {
    this.state = { ...this.state, ...next }
    this.listeners.forEach((listener) => listener())
  }
  private context(selected: OwnMembership | null, warning = this.state.warning) {
    const id = this.generation
    const pending = configurePrivateRequests(this.client && this.identity ? {
      workspaceId: selected?.workspace_id ?? null,
      accessToken: () => this.token(id),
      onFailure: (status) => {
        if (id !== this.generation) return
        if (status === 401) this.end('Your session has ended. Sign in again; no operation was retried.')
        else if (this.state.status === 'ready') void this.refreshAccess('Permissions changed. Access has been refreshed; no write was retried.')
      },
    } : null)
    if (pending) warning = `A save in ${pending.workspaceId ? `workspace ${pending.workspaceId}` : 'your account'} may have completed. Check the original workspace or membership list before retrying.`
    this.publish({ selected, version: this.state.version + 1, warning })
  }
  private reset() {
    this.generation++
    clearTimeout(this.timer)
    this.timer = undefined
    this.client?.clear()
    this.client = null
    this.identity = null
    this.renewal = null
    this.refreshing = null
    this.callbackActive = false
    try { this.host.clearTransient() } catch { /* Storage may be unavailable. */ }
    const pending = configurePrivateRequests(null)
    this.publish({ me: null, selected: null, version: this.state.version + 1, warning: pending ? 'A previous save may have completed. Check its original workspace before retrying.' : null })
  }
  end(message = 'You are signed out.') {
    this.reset()
    this.publish({ status: this.configuration.config ? 'signed-out' : 'setup', message: this.configuration.error ?? message })
  }
  cancelPending = () => {
    if (this.callbackActive || ['signing-in', 'callback', 'logging-out'].includes(this.state.status)) this.end('Sign-in or logout navigation was cancelled. You remain locally signed out.')
  }
  start(url: string) {
    if (!this.startup) this.startup = this.startOnce(url)
    return this.startup
  }
  private async startOnce(url: string) {
    const callback = new URL(url).pathname === '/auth/callback'
    if (callback) this.host.clearCallback()
    if (!this.configuration.config) return
    if (!callback) { this.end('Sign in to open workspace records.'); return }
    const id = ++this.generation
    this.callbackActive = true
    this.publish({ status: 'callback', message: 'Completing sign-in…' })
    try {
      this.client = this.factory()
      const identity = await bounded(this.client.callback(url), this.deadline)
      if (id !== this.generation) return
      this.identity = identity
      this.schedule()
      await this.refreshAccess()
      if (id === this.generation && this.state.status === 'ready') {
        // Internal navigation emits hashchange; the completed callback must
        // stop counting as pending before that event reaches cancelPending.
        this.callbackActive = false
        this.host.replace(safeReturnHash(this.identity?.returnHash))
      }
    } catch {
      if (id === this.generation) this.end('Sign-in could not be completed or was cancelled. Start a new sign-in; no provider details are displayed.')
    } finally { if (id === this.generation) this.callbackActive = false }
  }
  async signIn(returnHash: string) {
    if (!this.configuration.config || ['signing-in', 'callback', 'logging-out'].includes(this.state.status)) return
    if (this.host.origin() !== 'http://localhost:5173') {
      this.publish({ message: 'Open http://localhost:5173 before signing in. Login state cannot move between hostnames.' })
      return
    }
    this.reset()
    const id = this.generation
    this.publish({ status: 'signing-in', message: 'Opening Cognito sign-in…' })
    try {
      const client = this.factory()
      this.client = client
      const url = await bounded(client.signIn(safeReturnHash(returnHash)), this.deadline)
      if (id === this.generation && this.state.status === 'signing-in') {
        const target = new URL(url)
        if (target.origin + target.pathname !== this.configuration.config.domain + '/oauth2/authorize') throw new Error('Unsafe login navigation.')
        this.host.external(url)
      }
    } catch {
      if (id === this.generation) this.end('Sign-in could not start. Check configuration, browser storage and connection, then try again.')
    }
  }
  private schedule() {
    clearTimeout(this.timer)
    if (!this.identity) return
    this.timer = setTimeout(() => { void this.token(this.generation).catch(() => {}) }, Math.max(0, Math.min(2147483647, (this.identity.expiresAt - Date.now() / 1000 - 60) * 1000)))
  }
  private async token(id: number): Promise<string> {
    const client = this.client, identity = this.identity
    if (id !== this.generation || !client || !identity) throw new ApiFailure('unauthorized', 'Sign in again.', [], 401)
    if (identity.expiresAt > Date.now() / 1000 + 60) {
      const token = client.accessToken()
      if (token) return token
    }
    if (!this.renewal) {
      this.renewal = (async () => {
        try {
          const next = await bounded(client.renew(), this.deadline)
          if (id !== this.generation || client !== this.client) throw new Error('Obsolete renewal.')
          if (next.subject !== identity.subject || next.issuer !== identity.issuer || next.expiresAt <= Date.now() / 1000 + 60) throw new Error('Renewal did not extend this session.')
          this.identity = next
          this.schedule()
          const token = client.accessToken()
          if (!token) throw new Error('Missing access token.')
          return token
        } catch {
          if (id === this.generation) this.end('Session renewal failed. Sign in again; no operation was retried.')
          throw new ApiFailure('unauthorized', 'Sign in again.', [], 401)
        } finally { if (id === this.generation) this.renewal = null }
      })()
    }
    return this.renewal
  }
  refreshAccess(message = '') {
    if (this.refreshing) return this.refreshing
    if (!this.client || !this.identity) return Promise.resolve()
    const id = this.generation, previous = this.state.selected?.workspace_id
    const initially = this.state.me === null
    this.publish({ status: 'loading', message, me: null })
    this.context(null)
    this.refreshing = (async () => {
      try {
        const me = await this.loadMe()
        if (id !== this.generation) return
        if (me.user.issuer !== this.identity?.issuer || me.user.subject !== this.identity.subject) { this.end('The API identity did not match this sign-in. Sign in again.'); return }
        const selected = me.memberships.find((membership) => membership.workspace_id === previous) ?? (initially && me.memberships.length === 1 ? me.memberships[0] : null)
        this.publish({ me, status: 'ready', message })
        this.context(selected)
      } catch (error) {
        if (id !== this.generation) return
        if (error instanceof ApiFailure && error.status === 401) this.end('Your session has ended. Sign in again.')
        else this.publish({ status: 'access-error', me: null, message: 'Workspace access could not be loaded. Retry access information or sign out. No saved operation will be replayed.' })
      } finally { if (id === this.generation) this.refreshing = null }
    })()
    return this.refreshing
  }
  selectWorkspace(workspaceId: string) {
    if (this.state.status !== 'ready') return
    const selected = workspaceId ? this.state.me?.memberships.find((m) => m.workspace_id === workspaceId) : null
    if (workspaceId && !selected) return
    if (selected?.workspace_id === this.state.selected?.workspace_id) return
    this.context(selected ?? null)
    this.host.replace('#/account')
  }
  async logout() {
    if (!this.configuration.config) { this.end(); return }
    const revoke = this.client?.takeRevocation()
    this.reset()
    const id = this.generation
    this.publish({ status: 'logging-out', message: 'Locally signed out. Closing the Cognito session…' })
    try { if (revoke) await bounded(revoke(), this.deadline) } catch { /* Best effort; local cleanup already completed. */ }
    if (id === this.generation && this.state.status === 'logging-out') {
      try { this.host.external(cognitoLogoutUrl(this.configuration.config)) }
      catch { this.publish({ status: 'signed-out', message: 'Locally signed out. Cognito logout navigation failed; close its session separately.' }) }
    }
  }
}
