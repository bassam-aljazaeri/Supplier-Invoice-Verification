export type AuthConfig = { authority: string; clientId: string; domain: string; callbackUrl: string; logoutUrl: string }
export type AuthConfiguration = { config: AuthConfig; error: null } | { config: null; error: string }

export function readAuthConfig(settings: Record<string, unknown>): AuthConfiguration {
  const names = ['VITE_COGNITO_AUTHORITY', 'VITE_COGNITO_CLIENT_ID', 'VITE_COGNITO_DOMAIN', 'VITE_AUTH_CALLBACK_URL', 'VITE_AUTH_LOGOUT_URL'] as const
  const missing = names.filter((name) => typeof settings[name] !== 'string' || !(settings[name] as string).trim())
  if (missing.length) return { config: null, error: `Configure ${missing.join(', ')} using frontend/.env.example, then restart Vite. These settings are public identifiers, never secrets.` }
  const [authority, clientId, domain, callbackUrl, logoutUrl] = names.map((name) => settings[name] as string)
  try {
    const issuer = new URL(authority)
    const region = /^cognito-idp\.([a-z]{2}(?:-[a-z]+){1,3}-[1-9][0-9]*)\.amazonaws\.com(\.cn)?$/.exec(issuer.hostname)?.[1]
    if (!region || issuer.protocol !== 'https:' || issuer.username || issuer.password || issuer.port || issuer.search || issuer.hash
      || issuer.origin + issuer.pathname !== authority || !new RegExp(`^/${region}_[A-Za-z0-9]+$`).test(issuer.pathname)
      || issuer.hostname.endsWith('.cn') !== region.startsWith('cn-')) throw new Error()
    const login = new URL(domain)
    if (login.protocol !== 'https:' || login.origin !== domain || login.username || login.password || login.port || !login.hostname.includes('.')) throw new Error()
    if (!/^[A-Za-z0-9_+]{1,128}$/.test(clientId)) throw new Error()
    // This checkpoint supports only the reviewed local browser origin.
    if (callbackUrl !== 'http://localhost:5173/auth/callback' || logoutUrl !== 'http://localhost:5173/') throw new Error()
    return { config: { authority, clientId, domain, callbackUrl, logoutUrl }, error: null }
  } catch {
    return { config: null, error: 'Check the five public authentication settings: use the original regional HTTPS Cognito pool authority, a public client ID, an HTTPS login domain without a trailing slash, callback http://localhost:5173/auth/callback and logout http://localhost:5173/.' }
  }
}
