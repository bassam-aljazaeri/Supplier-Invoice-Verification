# Supplier-Invoice-Verification demo

This milestone is a local website for manually entered suppliers, purchase orders,
delivery records, and draft invoices stored in PostgreSQL. The example orders 10
keyboards at EUR 25, records delivery of 8, and invoices 10 with tax 0.00 and total
250.00. Extraction, automatic matching/discrepancy detection, authentication, and
approval remain later work. The seeded workspace is local demo context, not an
authentication or security boundary.

## Prepare the fictional demo

Use Docker Desktop with Linux containers, existing local database settings, and
Node.js 24/npm for the frontend. These **Windows host PowerShell commands** run
from the project directory; Alembic/Python execute in the **Linux API container**.
They intentionally initialize your chosen local demo database. For automated
verification that leaves development data untouched, run only
`.\scripts\check-backend.ps1`; its disposable stack is removed after verification.

```powershell
docker compose up --build -d
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
docker compose exec -T api python -m app.seed_demo
docker compose exec -T api python -m app.seed_demo
```

Both seed runs should succeed; the second preserves all IDs, timestamps, lines,
values, and counts. The entire fixture, including the fixed workspace, uses one
transaction. A conflict exits nonzero without overwrites or partial inserts.
Existing API-created demo identifiers with different IDs conflict deliberately.
Keep those records; review [the seed/conflict instructions](../README.md#repeatable-fictional-demo-step-36)
before choosing a fresh demo database. Do not remove development volumes.

In a second **Windows host PowerShell** terminal from the project directory:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Stop an existing Vite process before `npm ci`. Open
`http://127.0.0.1:5173/#/status`. These checks use saved fictional records and do
not require additional creates or edits.

## Short browser demonstration

1. On **Status**, verify the exact Supplier-Invoice-Verification name and healthy
   API/PostgreSQL/Redis results. Select **Refresh status**.
2. On **Suppliers**, open **DEMO-OFFICE-001 — Demo Office Supplies**. Check the
   fictional notes and linked **PO-DEMO-001** and **INV-DEMO-001** sections.
3. Open **PO-DEMO-001**. Expect date 2026-10-13, EUR, one Keyboard line, quantity
   10.000, unit price 25.0000, line total/subtotal 250.00, and a supplier link.
4. In its related deliveries, open **DR-DEMO-001**. Expect date 2026-10-14,
   Keyboard received quantity 8.000, and working order/supplier links. Browse the
   **Delivery records** list and return to the same receipt.
5. In the order's related invoices or **Invoices**, open **INV-DEMO-001**. Expect
   date 2026-10-15, due 2026-11-14, draft status, one Keyboard line invoicing
   10.000 at 25.0000, subtotal 250.00, explicit tax 0.00, and total 250.00.
   Verify the manually mapped order-line and supplier/order links.
6. Compare the three saved records: ordered 10, delivered 8, invoiced 10. The user
   can see the difference; no automatic discrepancy flag, matching result, or
   approval action is expected at this milestone.
7. Refresh a detail page; use browser Back/Forward and its copied deep link in a
   new tab. Direct fixture links include
   `http://127.0.0.1:5173/#/purchase-orders/20000000-0000-4000-8000-000000000001`,
   `http://127.0.0.1:5173/#/deliveries/30000000-0000-4000-8000-000000000001`, and
   `http://127.0.0.1:5173/#/invoices/40000000-0000-4000-8000-000000000001`.
   Confirm the same saved lines/values and readable layout with keyboard navigation
   and a narrow viewport. An unknown hash should show page not found.
8. Open `http://127.0.0.1:8000/docs`. Inspect a business endpoint's response examples:
   422 `validation_error`, 404 `not_found`, 409 `conflict`, 503
   `service_unavailable`, and 500 `internal_error`, each inside `error` with
   `message` and `details`. Runtime errors and health/readiness behavior are unchanged.

Record the browser, date, and observed outcomes in progress only after performing
these steps. Remaining creation, selector pagination, failed/uncertain saves,
obsolete responses, independent related-list failures, and accessibility scenarios
are listed in [README's website checklists](../README.md#delivery-record-and-draft-invoice-website-step-35b).
Use separate fictional `MANUAL-*`/`UI-*` identifiers in your chosen verification
database for write scenarios, preserving the reserved demo fixture.

## Automated verification and limits

Run `.\scripts\check-backend.ps1` from project-root PowerShell. It builds an
isolated stack, applies and verifies migrations, runs opted-in PostgreSQL tests,
seeds twice, prints live API IDs/decimal values, restarts API and PostgreSQL
without removing the volume, and verifies the same full snapshot after bounded
recovery. It retains dependency outage/recovery checks and removes only its
disposable resources. GitHub backend CI uses the same demo verification module.

These checks prove database/API persistence and repeatability. They do not prove
browser rendering or an online GitHub run. Actual automated results and pending
manual/online checks are recorded separately in [progress](progress.md).
