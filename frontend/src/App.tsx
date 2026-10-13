import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { parseHash, subscribeHashChange } from './navigation.ts'
import { newOrderDraft, newSupplierDraft } from './validation.ts'
import type { SaveFeedback } from './hooks/useBusiness.ts'
import Navigation from './components/Navigation.tsx'
import StatusPage from './pages/StatusPage.tsx'
import SupplierListPage from './pages/suppliers/SupplierListPage.tsx'
import SupplierNewPage from './pages/suppliers/SupplierNewPage.tsx'
import SupplierDetailPage from './pages/suppliers/SupplierDetailPage.tsx'
import PurchaseOrderListPage from './pages/purchase-orders/PurchaseOrderListPage.tsx'
import PurchaseOrderNewPage from './pages/purchase-orders/PurchaseOrderNewPage.tsx'
import PurchaseOrderDetailPage from './pages/purchase-orders/PurchaseOrderDetailPage.tsx'
import './App.css'

const subscribe = (listener: () => void) => subscribeHashChange(listener)
const snapshot = () => window.location.hash

function App() {
  const hash = useSyncExternalStore(subscribe, snapshot, () => '')
  const route = parseHash(hash)
  const content = useRef<HTMLElement>(null)
  // Drafts and failed-save feedback survive page changes, but never enter storage.
  const [supplierDraft, setSupplierDraft] = useState(newSupplierDraft)
  const [orderDraft, setOrderDraft] = useState(newOrderDraft)
  const [supplierFeedback, setSupplierFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  const [orderFeedback, setOrderFeedback] = useState<SaveFeedback>({ pending: false, error: null })
  useEffect(() => { content.current?.focus() }, [hash])

  let page
  switch (route.kind) {
    case 'status': page = <StatusPage />; break
    case 'supplier-list': page = <SupplierListPage page={route.page} />; break
    case 'supplier-detail': page = <SupplierDetailPage id={route.id} page={route.page} />; break
    case 'supplier-new': page = <SupplierNewPage draft={supplierDraft} setDraft={setSupplierDraft} feedback={supplierFeedback} setFeedback={setSupplierFeedback} />; break
    case 'order-list': page = <PurchaseOrderListPage page={route.page} />; break
    case 'order-detail': page = <PurchaseOrderDetailPage id={route.id} />; break
    case 'order-new': page = <PurchaseOrderNewPage draft={orderDraft} setDraft={setOrderDraft} feedback={orderFeedback} setFeedback={setOrderFeedback} />; break
    default: page = <section className="business-panel"><h2>Page not found</h2><p>This address does not match an available page, or its page parameters are invalid.</p><a href="#/status">Open Status</a></section>
  }
  return <div className="page-shell">
    <a className="skip-link" href="#page-content" onClick={(event) => { event.preventDefault(); content.current?.focus() }}>Skip to content</a>
    <header className="page-header"><p className="eyebrow">Local demo</p><h1>Supplier-Invoice-Verification</h1><Navigation route={route} /></header>
    <main id="page-content" ref={content} tabIndex={-1} key={hash}>{page}</main>
    <footer className="page-footer"><span>Supplier-Invoice-Verification</span><span>Local services at 127.0.0.1</span></footer>
  </div>
}

export default App
