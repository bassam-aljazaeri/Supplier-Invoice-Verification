import { useSession } from '../authContext.tsx'

export default function SignInPage({ returnHash = '#/account' }: { returnHash?: string }) {
  const { session, status, message } = useSession()
  const busy = ['signing-in', 'callback', 'logging-out'].includes(status)
  return <section className="business-panel" aria-busy={busy}><h2>{status === 'setup' ? 'Set up browser sign-in' : 'Sign in'}</h2>
    <p role={status === 'setup' ? 'alert' : 'status'}>{message || 'Sign in with the configured Cognito account to open your workspaces.'}</p>
    {status !== 'setup' && (busy ? <button type="button" onClick={session.cancelPending}>Cancel</button> : <button className="primary-button" type="button" onClick={() => { void session.signIn(returnHash) }}>Continue to Cognito</button>)}
    <p>Use <a href="http://localhost:5173/">http://localhost:5173/</a> for sign-in. No passwords or tokens are entered here.</p>
    <p>Reloading can require another login redirect. Unsaved forms are kept only while this page remains open.</p>
    <a href="#/status">Open public service status</a>
  </section>
}
