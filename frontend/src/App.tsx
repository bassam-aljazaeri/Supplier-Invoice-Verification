import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { ReactNode } from 'react'
import { parseHash, subscribeHashChange } from './navigation.ts'
import type { Route } from './navigation.ts'
import { useSession } from './authContext.tsx'
import { canCreate, canManage } from './authTypes.ts'
import WorkspaceSelector from './components/WorkspaceSelector.tsx'
import SignInPage from './pages/SignInPage.tsx'
import AccountPage from './pages/AccountPage.tsx'
import WorkspaceNewPage from './pages/WorkspaceNewPage.tsx'
import MembershipsPage from './pages/MembershipsPage.tsx'
import { newDeliveryDraft, newInvoiceDraft, newOrderDraft, newSupplierDraft } from './validation.ts'
import type { SaveFeedback } from './hooks/useBusiness.ts'
import Navigation from './components/Navigation.tsx'
import StatusPage from './pages/StatusPage.tsx'
import SupplierListPage from './pages/suppliers/SupplierListPage.tsx'
import SupplierNewPage from './pages/suppliers/SupplierNewPage.tsx'
import SupplierDetailPage from './pages/suppliers/SupplierDetailPage.tsx'
import PurchaseOrderListPage from './pages/purchase-orders/PurchaseOrderListPage.tsx'
import PurchaseOrderNewPage from './pages/purchase-orders/PurchaseOrderNewPage.tsx'
import PurchaseOrderDetailPage from './pages/purchase-orders/PurchaseOrderDetailPage.tsx'
import DeliveryListPage from './pages/deliveries/DeliveryListPage.tsx'
import DeliveryNewPage from './pages/deliveries/DeliveryNewPage.tsx'
import DeliveryDetailPage from './pages/deliveries/DeliveryDetailPage.tsx'
import InvoiceListPage from './pages/invoices/InvoiceListPage.tsx'
import InvoiceNewPage from './pages/invoices/InvoiceNewPage.tsx'
import InvoiceDetailPage from './pages/invoices/InvoiceDetailPage.tsx'
import './App.css'

const subscribe = (listener: () => void) => subscribeHashChange(listener)
const snapshot = () => window.location.hash

function BusinessPages({ route, hash, override }: { route: Route; hash: string; override?: ReactNode }) {
  // Drafts and failed-save feedback survive page changes, but never enter storage.
  const [supplierDraft, setSupplierDraft] = useState(newSupplierDraft)
  const [orderDraft, setOrderDraft] = useState(newOrderDraft)
  const [deliveryDraft, setDeliveryDraft] = useState(newDeliveryDraft)
  const [invoiceDraft, setInvoiceDraft] = useState(newInvoiceDraft)
  const [supplierFeedback, setSupplierFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const [orderFeedback, setOrderFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const [deliveryFeedback, setDeliveryFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const [invoiceFeedback, setInvoiceFeedback] = useState<SaveFeedback>({ pending: false, error: null })

  let page
  switch (route.kind) {
    case 'status': page = <StatusPage />; break
    case 'supplier-list': page = <SupplierListPage page={route.page} />; break
    case 'supplier-detail': page = <SupplierDetailPage id={route.id} page={route.page} />; break
    case 'supplier-new': page = <SupplierNewPage draft={supplierDraft} setDraft={setSupplierDraft} feedback={supplierFeedback} setFeedback={setSupplierFeedback} />; break
    case 'order-list': page = <PurchaseOrderListPage page={route.page} />; break
    case 'order-detail': page = <PurchaseOrderDetailPage id={route.id} />; break
    case 'order-new': page = <PurchaseOrderNewPage draft={orderDraft} setDraft={setOrderDraft} feedback={orderFeedback} setFeedback={setOrderFeedback} />; break
    case 'delivery-list': page = <DeliveryListPage page={route.page} />; break
    case 'delivery-detail': page = <DeliveryDetailPage id={route.id} />; break
    case 'delivery-new': page = <DeliveryNewPage draft={deliveryDraft} setDraft={setDeliveryDraft} feedback={deliveryFeedback} setFeedback={setDeliveryFeedback} />; break
    case 'invoice-list': page = <InvoiceListPage page={route.page} />; break
    case 'invoice-detail': page = <InvoiceDetailPage id={route.id} />; break
    case 'invoice-new': page = <InvoiceNewPage draft={invoiceDraft} setDraft={setInvoiceDraft} feedback={invoiceFeedback} setFeedback={setInvoiceFeedback} />; break
    default: page = <section className="business-panel"><h2>Page not found</h2><p>This address does not match an available page, or its page parameters are invalid.</p><a href="#/status">Open Status</a></section>
  }
  return <div key={hash}>{override ?? page}</div>
}

function App() {
  const hash = useSyncExternalStore(subscribe, snapshot, () => '')
  const route = parseHash(hash)
  const auth = useSession()
  const content = useRef<HTMLElement>(null)
  useEffect(() => { content.current?.focus() }, [hash, auth.version])
  let page
  if (route.kind === 'status') page = <StatusPage />
  else if (['setup', 'signed-out', 'signing-in', 'callback', 'logging-out'].includes(auth.status)) page = <SignInPage returnHash={hash} />
  else if (auth.status === 'loading') page = <section className="business-panel" role="status"><h2>Loading workspace access</h2><p>Previous private views have been cleared.</p></section>
  else if (auth.status === 'access-error') page = <section className="business-panel"><h2>Workspace access unavailable</h2><p role="alert">{auth.message}</p><button type="button" onClick={() => { void auth.session.refreshAccess() }}>Retry access information</button></section>
  else if (route.kind === 'workspace-new') page = <WorkspaceNewPage key={auth.version} />
  else if (route.kind === 'account' || route.kind === 'signin' || !auth.selected) page = <AccountPage key={auth.version} />
  else if (route.kind === 'memberships') page = canManage(auth.selected.role) ? <MembershipsPage key={auth.version} /> : <section className="business-panel"><h2>Administrator access required</h2><a href="#/account">Open account</a></section>
  else if (route.kind.endsWith('-new') && !canCreate(auth.selected.role)) page = <section className="business-panel"><h2>Read-only access</h2><p>Your approver membership can read records. Administrators and accountants can create them.</p><a href="#/suppliers">Open records</a></section>
  else page = undefined
  return <div className="page-shell">
    <a className="skip-link" href="#page-content" onClick={(event) => { event.preventDefault(); content.current?.focus() }}>Skip to content</a>
    <header className="page-header"><p className="eyebrow">Workspace records</p><h1>Supplier-Invoice-Verification</h1><Navigation route={route} /><WorkspaceSelector /></header>
    {auth.status === 'setup' && route.kind === 'status' && <p role="status">Browser sign-in needs configuration. <a href="#/signin">Review the public setup settings</a>. Service status remains public.</p>}
    {auth.warning && <p className="request-error" role="alert">{auth.warning}</p>}
    {auth.status === 'ready' && auth.message && <p role="status">{auth.message}</p>}
    <main id="page-content" ref={content} tabIndex={-1}>{auth.status === 'ready' && auth.selected ? <BusinessPages key={auth.version} route={route} hash={hash} override={page} /> : page}</main>
    <footer className="page-footer"><span>Supplier-Invoice-Verification</span><span>Local services on localhost</span></footer>
  </div>
}

export default App
