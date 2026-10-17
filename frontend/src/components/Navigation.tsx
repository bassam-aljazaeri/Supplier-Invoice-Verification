import type { Route } from '../navigation.ts'
import { useSession } from '../authContext.tsx'
import { canManage } from '../authTypes.ts'

export default function Navigation({ route }: { route: Route }) {
  const { session, status, selected } = useSession()
  const links = [{ hash: '#/status', title: 'Status', active: route.kind === 'status' },
    { hash: '#/suppliers', title: 'Suppliers', active: route.kind.startsWith('supplier-') },
    { hash: '#/purchase-orders', title: 'Purchase orders', active: route.kind.startsWith('order-') },
    { hash: '#/deliveries', title: 'Delivery records', active: route.kind.startsWith('delivery-') },
    { hash: '#/invoices', title: 'Invoices', active: route.kind.startsWith('invoice-') }]
  const authenticated = ['ready', 'loading', 'access-error'].includes(status)
  return <nav className="site-navigation" aria-label="Main navigation">{links.filter((link) => link.hash === '#/status' || (status === 'ready' && selected)).map((link) => <a key={link.hash} href={link.hash} aria-current={link.active ? 'page' : undefined}>{link.title}</a>)}
    <a href={authenticated ? '#/account' : '#/signin'}>{authenticated ? 'Account' : 'Sign in'}</a>
    {status === 'ready' && canManage(selected?.role) && <a href="#/memberships" aria-current={route.kind === 'memberships' ? 'page' : undefined}>Memberships</a>}
    {authenticated && <button type="button" onClick={() => { void session.logout() }}>Sign out</button>}
  </nav>
}
