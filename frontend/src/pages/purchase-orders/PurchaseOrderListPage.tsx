import type { OrderParams } from '../../types.ts'
import { listHash, navigate } from '../../navigation.ts'
import PurchaseOrderList from '../../components/PurchaseOrderList.tsx'

export default function PurchaseOrderListPage({ page }: { page: OrderParams }) {
  return <section className="business-panel"><div className="panel-heading"><h2>Purchase orders</h2><a className="button-link" href="#/purchase-orders/new">Create purchase order</a></div>
    {page.supplier_id && <p>Showing orders for <a href={`#/suppliers/${page.supplier_id}`}>this supplier</a>. <a href="#/purchase-orders">Show all orders</a></p>}
    <PurchaseOrderList page={page} onPage={(offset) => navigate(listHash('purchase-orders', { ...page, offset }))} />
  </section>
}
