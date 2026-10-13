import type { InvoiceParams } from '../../types.ts'
import { listHash, navigate } from '../../navigation.ts'
import InvoiceList from '../../components/InvoiceList.tsx'

export default function InvoiceListPage({ page }: { page: InvoiceParams }) {
  return <section className="business-panel">
    <div className="panel-heading"><h2>Invoices</h2><a className="button-link" href="#/invoices/new">Create invoice</a></div>
    <p>Manually entered invoices are saved as drafts. Open an invoice to view its saved totals.</p>
    {(page.supplier_id || page.purchase_order_id) && <p>
      Showing invoices{page.supplier_id && <> for <a href={`#/suppliers/${page.supplier_id}`}>this supplier</a></>}{page.purchase_order_id && <> linked to <a href={`#/purchase-orders/${page.purchase_order_id}`}>this purchase order</a></>}. <a href="#/invoices">Show all invoices</a>
    </p>}
    <InvoiceList page={page} onPage={(offset) => navigate(listHash('invoices', { ...page, offset }))} />
  </section>
}
