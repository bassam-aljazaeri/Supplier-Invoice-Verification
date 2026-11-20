# Supplier-Invoice-Verification demo

Milestone 5 is an authenticated local website for workspace-owned manual records
and private document upload, background validation and authorized download.
**Accepted means file validation passed, not invoice approval.** An upload does
not create or link an invoice. OCR/extraction, automatic matching/discrepancy
detection and approval remain later work.

Normal development uses private **local storage**. Follow
[normal local startup after S3 cleanup](../README.md#start-normal-local-development-after-the-s3-smoke-test)
to start API, PostgreSQL, Redis, worker, dispatcher and the standard frontend.
Use fresh PowerShell terminals, the original local project/settings/volumes,
and `http://localhost:5173`; the normal frontend proxies to port 8000. Do not
reuse the removed smoke project's settings, port-8001 proxy or S3-backed database.
The commands and walkthroughs below are operator instructions, not new runs
performed during Step 5.7 preparation.

## Short document-upload demonstration

Use an administrator/accountant account in an accessible fictional workspace,
or create a new workspace after signing in. Approvers can read and download
accepted files but cannot upload or retry processing. Signing in alone does
not grant access to the optional `local-demo` fixture.

Generate one fictional single-page PDF with **Windows PowerShell** at the
repository root. Python executes inside the **Linux API container** and only
generates bytes; it does not seed or query business records. The commands use
the standard local project; substitute your existing development project name
if it differs, as described in README.

```powershell
$documentDemoBase64 = docker compose --project-name supplier-invoice-verification --env-file .\.env -f .\compose.yaml exec -T api python -c "from tests.document_helpers import pdf; import base64; print(base64.b64encode(pdf()).decode())"
if ($LASTEXITCODE -ne 0) { throw 'Fictional PDF generation failed' }
$documentDemoPdf = Join-Path ([IO.Path]::GetTempPath()) ('siv-fictional-invoice-' + [Guid]::NewGuid().ToString('N') + '.pdf')
[IO.File]::WriteAllBytes($documentDemoPdf, [Convert]::FromBase64String(($documentDemoBase64 -join '')))
$documentDemoPdf
Get-FileHash -LiteralPath $documentDemoPdf -Algorithm SHA256
```

1. Sign in at `http://localhost:5173`, select the intended workspace, open
   **Documents**, then **Upload document**. Choose the generated PDF and upload
   it once. Use fictional PDF/JPEG/PNG only, 1-5,000,000 bytes; PDFs must have one
   page and no encryption.
2. Follow the saved document to its detail page. The flow is fictional file
   **→ queued → processing → accepted → authorized download**. Fast processing
   may finish between polls, so every intermediate state need not appear.
   Use **Refresh status** if automatic polling pauses; do not upload again just
   because the file remains queued.
3. At **accepted**, check the file-validation explanation and document/workspace
   metadata. No invoice, extracted field, matching result or approval is created.
4. Choose **Download accepted document**. The app requests a fresh grant and,
   in normal local mode, fetches the attachment with current bearer/workspace
   authorization. Expect `document-{document-id}.pdf`; no inline preview or
   displayed download ticket. Rejected/nonterminal files cannot be downloaded.
5. Save the attachment, then compare its bytes with the original:

   ```powershell
   $documentDemoDownload = Read-Host 'Full path to the downloaded fictional PDF'
   $documentDemoOriginalHash = (Get-FileHash -LiteralPath $documentDemoPdf -Algorithm SHA256).Hash
   $documentDemoDownloadHash = (Get-FileHash -LiteralPath $documentDemoDownload -Algorithm SHA256).Hash
   if ($documentDemoOriginalHash -ne $documentDemoDownloadHash) { throw 'Downloaded PDF does not match' }
   'Original and downloaded PDF SHA-256 hashes match.'
   ```

The backend checks current workspace membership and accepted status; selecting
another workspace does not grant access to this document. An approver in the same
workspace can download the accepted file, with no Upload control. Optional S3
uses a short-lived external grant instead of the local-content route; never
copy/log its signed URL or send app authentication headers to S3.

## Prepare the optional fictional manual-record demo

The retained manual fixture orders 10 keyboards at EUR 25, records delivery of 8,
and invoices 10 with tax 0.00 and total 250.00. It is separate from document upload.
Use an account with membership in the fixed `local-demo` workspace; see
[existing membership/bootstrap instructions](../README.md#user-and-membership-persistence-step-43)
if needed. No manual fixture or membership bootstrap is required for the document
demo in your own newly created workspace.

Use Docker Desktop with Linux containers, existing local database settings, and
Node.js 24/npm for the frontend. These **Windows host PowerShell commands** run
from the project directory; Alembic/Python execute in the **Linux API container**.
They intentionally initialize your chosen local demo database. For automated
verification that leaves development data untouched, run only
`.\scripts\check-backend.ps1`; its disposable stack is removed after verification.

```powershell
docker compose --profile processing up --build -d
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
`http://localhost:5173/#/status`. These checks use saved fictional records and do
not require additional creates or edits.

## Short manual-record browser demonstration

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
   `http://localhost:5173/#/purchase-orders/20000000-0000-4000-8000-000000000001`,
   `http://localhost:5173/#/deliveries/30000000-0000-4000-8000-000000000001`, and
   `http://localhost:5173/#/invoices/40000000-0000-4000-8000-000000000001`.
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

Milestone 5 checks also exercise private local storage, the actual worker/parser,
durable dispatch, broker outage/message-loss/interruption recovery and scoped
document APIs. Automated S3 tests use Stubber, controlled objects and loopback
HTTP streams; they do not use AWS. Prior backend/frontend suite results in
[progress](progress.md) are historical evidence, not suites rerun for these docs.

Separately, the user completed the live S3 upload and processing retry after the
reader fix, reached Accepted, and downloaded an authorized PDF with matching
SHA-256. The user reported removing the isolated stack/volumes, dedicated test
object/bucket, IAM role and temporary credentials. This operator report is
separate from automated simulations and has not been rechecked against AWS here.
Online GitHub CI remains pending on the eventual submitted revision.

Known limits remain: no OCR/extraction or invoice approval; S3 orphan listing/
deletion is disabled and abandoned remote bytes may remain until reviewed operator
cleanup. Linux parser resource/network restrictions are limited containment,
not a complete sandbox or malware guarantee. The local worker still runs as root
and reports Celery's superuser warning. This is a fictional demonstration, not a
production-ready financial-data service.
