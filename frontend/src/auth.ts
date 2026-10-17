import { InMemoryWebStorage, Log, OidcClient, UserManager, WebStorageStateStore } from 'oidc-client-ts'
import type { OidcMetadata, User, UserManagerSettings } from 'oidc-client-ts'
import type { AuthConfig } from './authConfig.ts'
import { safeReturnHash } from './navigation.ts'

Log.setLevel(Log.NONE)
export const STATE_PREFIX = 'siv.pkce.'
export type BrowserIdentity = { issuer: string; subject: string; expiresAt: number; returnHash?: string }
export interface AuthClient {
  signIn(returnHash: string): Promise<string>
  callback(url: string): Promise<BrowserIdentity>
  renew(): Promise<BrowserIdentity>
  accessToken(): string | null
  clear(): void
  takeRevocation(): () => Promise<void>
}

export async function bounded<T>(operation: Promise<T>, milliseconds = 10000): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([operation, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error('Authentication deadline reached.')), milliseconds) })])
  } finally { clearTimeout(timer) }
}

export function clearLoginState(storage: Storage) {
  for (let i = storage.length - 1; i >= 0; i--) {
    const key = storage.key(i)
    if (key?.startsWith(STATE_PREFIX)) storage.removeItem(key)
  }
}

export function oidcSettings(config: AuthConfig, storage: Storage, memory = new InMemoryWebStorage()): UserManagerSettings {
  return {
    authority: config.authority, client_id: config.clientId, redirect_uri: config.callbackUrl,
    response_type: 'code', response_mode: 'query', scope: 'openid', disablePKCE: false,
    userStore: new WebStorageStateStore({ store: memory, prefix: 'siv.user.' }),
    stateStore: new WebStorageStateStore({ store: storage, prefix: STATE_PREFIX }),
    staleStateAgeInSeconds: 900, automaticSilentRenew: false, monitorSession: false,
    loadUserInfo: false, validateSubOnSilentRenew: true, revokeTokenTypes: ['refresh_token'],
    requestTimeoutInSeconds: 10, silentRequestTimeoutInSeconds: 10,
    fetchRequestCredentials: 'omit', refreshTokenAllowedScope: 'openid',
    metadataSeed: { revocation_endpoint: config.domain + '/oauth2/revoke' },
  }
}

export function validateMetadata(metadata: Partial<OidcMetadata>, config: AuthConfig) {
  if (metadata.issuer !== config.authority
    || metadata.authorization_endpoint !== config.domain + '/oauth2/authorize'
    || metadata.token_endpoint !== config.domain + '/oauth2/token'
    || metadata.revocation_endpoint !== config.domain + '/oauth2/revoke'
    || metadata.jwks_uri !== config.authority + '/.well-known/jwks.json') throw new Error('Unexpected identity-provider metadata.')
}

export function cognitoLogoutUrl(config: AuthConfig) {
  const url = new URL('/logout', config.domain)
  url.searchParams.set('client_id', config.clientId)
  url.searchParams.set('logout_uri', config.logoutUrl)
  return url.href
}

export function createAuthClient(config: AuthConfig, storage: Storage): AuthClient {
  const memory = new InMemoryWebStorage()
  const settings = oidcSettings(config, storage, memory)
  const manager = new UserManager(settings)
  let current: User | null = null
  let live = true
  const metadata = async () => {
    const result = await manager.metadataService.getMetadata()
    validateMetadata(result, config)
    return result
  }
  const accept = (user: User | null): BrowserIdentity => {
    if (!live || !user || !user.id_token || !user.access_token || user.token_type.toLowerCase() !== 'bearer'
      || user.profile.iss !== config.authority || user.profile.aud !== config.clientId
      || typeof user.profile.sub !== 'string' || !user.profile.sub.trim()
      || !Number.isFinite(user.expires_at) || user.expires_at! <= Date.now() / 1000
      || (current && current.profile.sub !== user.profile.sub)) throw new Error('Invalid authentication result.')
    current = user
    const state = user.state as { returnHash?: unknown } | undefined
    return { issuer: user.profile.iss, subject: user.profile.sub, expiresAt: user.expires_at!, returnHash: safeReturnHash(state?.returnHash) }
  }
  return {
    async signIn(returnHash) {
      clearLoginState(storage)
      const discovered = await bounded(metadata())
      if (!live) throw new Error('Cancelled sign-in.')
      // The controller owns navigation AFTER its completion guard. The library
      // still generates/stores state, nonce and PKCE and validates the callback.
      const request = await bounded(new OidcClient({ ...settings, metadata: discovered }).createSigninRequest({
        state: { returnHash: safeReturnHash(returnHash) }, nonce: crypto.randomUUID(), request_type: 'si:r',
      }))
      if (!live) { storage.removeItem(STATE_PREFIX + request.state.id); throw new Error('Cancelled sign-in.') }
      return request.url
    },
    async callback(url) {
      const address = new URL(url)
      if (address.origin + address.pathname !== config.callbackUrl || address.hash || [...address.searchParams.keys()].some((key) => address.searchParams.getAll(key).length !== 1)) throw new Error('Invalid callback address.')
      await bounded(metadata())
      await manager.clearStaleState()
      if (!live) throw new Error('Cancelled sign-in.')
      return accept(await bounded(manager.signinRedirectCallback(url)))
    },
    async renew() {
      // signinSilent uses refresh_token when present. Never permit its iframe fallback.
      if (!live || !current?.refresh_token) throw new Error('Sign in again.')
      await bounded(metadata())
      if (!live) throw new Error('Cancelled renewal.')
      return accept(await bounded(manager.signinSilent({ silentRequestTimeoutInSeconds: 10 })))
    },
    accessToken: () => live ? current?.access_token ?? null : null,
    clear() {
      live = false
      current = null
      memory.clear()
      manager.stopSilentRenew()
      manager.events.unload()
    },
    takeRevocation() {
      const refresh = current?.refresh_token
      return async () => {
        if (refresh) await bounded(new OidcClient({ ...settings, metadata: { issuer: config.authority, revocation_endpoint: config.domain + '/oauth2/revoke' } }).revokeToken(refresh, 'refresh_token'))
      }
    },
  }
}
