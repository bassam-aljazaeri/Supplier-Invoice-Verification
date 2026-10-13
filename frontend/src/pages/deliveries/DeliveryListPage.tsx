import type { DeliveryParams } from '../../types.ts'
import { listHash, navigate } from '../../navigation.ts'
import DeliveryList from '../../components/DeliveryList.tsx'

export default function DeliveryListPage({ page }: { page: DeliveryParams }) {
  return <section className="business-panel">
    <div className="panel-heading"><h2>Delivery records</h2><a className="button-link" href="#/deliveries/new">Create delivery record</a></div>
    {page.purchase_order_id && <p>Showing deliveries for <a href={`#/purchase-orders/${page.purchase_order_id}`}>this purchase order</a>. <a href="#/deliveries">Show all deliveries</a></p>}
    <DeliveryList page={page} onPage={(offset) => navigate(listHash('deliveries', { ...page, offset }))} />
  </section>
}
