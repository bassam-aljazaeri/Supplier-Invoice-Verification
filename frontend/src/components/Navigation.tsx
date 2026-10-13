import type { Route } from '../navigation.ts'

export default function Navigation({ route }: { route: Route }) {
  const links = [{ hash: '#/status', title: 'Status', active: route.kind === 'status' },
    { hash: '#/suppliers', title: 'Suppliers', active: route.kind.startsWith('supplier-') },
    { hash: '#/purchase-orders', title: 'Purchase orders', active: route.kind.startsWith('order-') },
    { hash: '#/deliveries', title: 'Delivery records', active: route.kind.startsWith('delivery-') },
    { hash: '#/invoices', title: 'Invoices', active: route.kind.startsWith('invoice-') }]
  return <nav className="site-navigation" aria-label="Main navigation">{links.map((link) => <a key={link.hash} href={link.hash} aria-current={link.active ? 'page' : undefined}>{link.title}</a>)}</nav>
}
