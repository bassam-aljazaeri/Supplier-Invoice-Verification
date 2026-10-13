# Supplier-Invoice-Verification

AI-assisted supplier invoice extraction, matching, review, and approval.

## Status
The local website has Status, supplier, purchase-order, delivery-record, and
draft-invoice pages. These APIs store records in PostgreSQL. Step 3.5B adds
delivery/invoice list, creation, detail, and linked-record views. Full demo seeding,
automatic matching, and the later review/approval workflow remain future work.

## First release
English invoices in EUR; one purchase order per invoice; single-page
PDF/JPEG/PNG uploads up to 5 MB; human approval before export.

## Development
Built step by step using React, FastAPI, PostgreSQL, and Docker.
See docs/scope.md and docs/progress.md.

Only fictional or explicitly licensed sample data belongs in this repository.

## Local backend foundation (Step 2A)

The local API, PostgreSQL, and Redis run in Docker. No host Python installation
is needed. Copy `.env.example` to `.env` and replace the password placeholder
with a strong local-only password before starting the stack.

From PowerShell in the project directory:

```powershell
Copy-Item .env.example .env
# Edit .env and set POSTGRES_PASSWORD before continuing.
docker compose up --build -d
docker compose exec api pytest -q
docker compose logs -f api
docker compose down
```

The API is available at `http://127.0.0.1:8000/health`. The readiness endpoint
at `/ready` checks PostgreSQL and Redis and returns HTTP 503 if either is down.
The database contents remain in a named Docker volume when the stack stops.

## Local frontend foundation (Step 2B)

Start the backend stack as described above, then open a second PowerShell
terminal in the project directory and run (checked with Node.js 24 and npm 11):

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The status page calls `/api/health` and `/api/ready`
on the Vite server. Vite forwards those requests to the API at
`http://127.0.0.1:8000`, removes the `/api` prefix, and sends `/health` or
`/ready` to FastAPI. The server binds only to `127.0.0.1:5173` and refuses
to start if that port is occupied.

The page checks on load and when you select **Refresh status**. API health,
PostgreSQL readiness, and Redis readiness appear separately. A readiness
HTTP 503 response still supplies the individual dependency results. Each
request has a five-second timeout, including reading its JSON body. Refresh
is disabled until both requests finish; use it again after restoring a service.

From PowerShell in the `frontend` directory, run the checks:

```powershell
npm.cmd run build
npm.cmd run lint
npm.cmd test
```

The tests use Node.js 24's built-in TypeScript support and test runner, with
simulated failed requests and recovery. Keep `package-lock.json` in version
control; `node_modules` and `dist` are ignored. The `/api` proxy is for the
Vite development server; the production build needs its own API routing.

## Automated checks (Step 2C)

`.github/workflows/ci.yml` runs for pull requests targeting `main` and pushes
to `main`, `feat/local-foundation`, or `feat/manual-invoice-workflow`. Both jobs use GitHub-hosted Ubuntu 24.04
runners and `contents: read` permissions. Checkout does not retain credentials.
The official checkout and setup-node actions are pinned to verified release
commits ([checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1)
and [setup-node v7.0.0](https://github.com/actions/setup-node/releases/tag/v7.0.0)).

The frontend job installs with Node.js 24 and `npm ci`, then runs lint,
the status request tests, and the production build. The backend job builds
the existing Dockerfile, which uses `uv sync --locked` with `backend/uv.lock`.
It combines `compose.yaml` and `compose.ci.yaml`, generates temporary database
settings on the runner, and uses a unique Compose project name for each run
and attempt. The CI override removes the API host port and source mount;
checks use real HTTP inside the Linux API container.

Compose startup waits at most 90 seconds for running/healthy services.
The HTTP checker has a 60-second budget and verifies both status codes and
complete JSON results. After pytest, the backend job initializes only the demo
workspace twice to check repeatability, then stops its PostgreSQL and
Redis containers, checks that `/health` remains HTTP 200 while `/ready` reports
HTTP 503 with both dependencies unavailable, and restarts them to check recovery.
Failure logs are printed, and an `always()` cleanup step removes the project's
containers, network, volumes, and temporary environment file. Job and step time
limits provide additional bounds. No repository secrets, AWS access, paid APIs,
or deployment permissions are used.

To repeat the checks locally, run these **Windows host PowerShell commands**
from the project directory. Stop a running Vite server before `npm ci` so
Windows can replace its native modules.

```powershell
Set-Location frontend
npm.cmd ci --no-audit --no-fund
npm.cmd run lint
npm.cmd test
npm.cmd run build
Set-Location ..
.\scripts\check-backend.ps1
```

The backend script creates its own temporary database settings and unique
Compose project, prints logs on failure, and cleans up in a `finally` block.
It runs `pytest -q` and `python scripts/check_endpoints.py` **inside the Linux
API container**. It uses no published API port, so an existing development
stack can remain running. It deletes only its disposable project's volumes.
Docker Desktop with Linux containers and Compose 2.24.4 or newer are required
for the CI override tags. Both committed dependency lockfiles remain in use.

Local checks evaluate the current Windows working files and Docker Desktop
containers. GitHub Actions evaluates the submitted commit on fresh Ubuntu
virtual machines, installs its own dependencies, and attaches check results to
the push or pull request. Local success is recorded in `docs/progress.md`;
**GitHub CI remains pending until an online run is verified**.

## PostgreSQL schema and isolated checks (Step 3.2)

The shared database module keeps the existing safe URL construction and bounded
connection settings. Its synchronous session dependency closes every request's
session, rolls back on failure, and never commits automatically. Business code
must commit explicitly. Application startup does not create tables or seed data.
`/health` and `/ready` keep their existing response bodies and behavior; readiness
checks connectivity, not migration state or the presence of a workspace.

The initial migration `0001_manual_records` creates `workspaces`, `suppliers`,
`purchase_orders`, `purchase_order_lines`, `delivery_receipts`,
`delivery_receipt_lines`, `invoices`, and `invoice_lines`. All business rows carry
workspace ownership. Composite foreign keys enforce the same workspace, supplier,
order, and line ownership described in [the blueprint](docs/manual-workflow.md).
Invoice mappings require both mapping IDs or neither; an unmapped line is valid
even when its invoice has an order. No discrepancy comparisons are implemented.

UUIDs and timestamps have PostgreSQL defaults, and invoice status defaults to
`draft` even for direct SQL inserts. Numeric columns use the blueprint's exact
decimal types, nonnegative/positive checks, and finite upper bounds. Required text
must be trimmed and nonblank. Business dates are valid calendar dates in years
0001-9999, with an optional due date no earlier than the invoice date.
PostgreSQL itself coerces input to a numeric column's scale. Step 3.3's request
schemas additionally reject excess input scale and enforce line-count limits;
its purchase-order service calculates and rounds line totals and subtotal.
Step 3.4 adds invoice schemas and calculations using the same decimal rules.

ORM parent relationships write their designated IDs while keeping workspace IDs
explicit. Workspace collections and order-line lookup relationships are read-only
views; set the two optional invoice mapping IDs together explicitly. Composite
joins follow [SQLAlchemy's overlapping-foreign-key guidance](https://docs.sqlalchemy.org/en/20/orm/join_conditions.html#overlapping-foreign-keys).
SQLAlchemy warnings fail the tests rather than being suppressed.

### Build and migrate the local development database

These are **Windows host PowerShell commands** from the project directory, using
your existing local development settings. The `exec` commands run Alembic inside
the **Linux API container**. Rebuild before migrating: only `backend/app` is
mounted in development, while dependencies and migrations come from the image.

```powershell
docker compose up --build -d
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
```

Expect revision `0001_manual_records (head)`. Running `upgrade head` again is
harmless. This applies forward schema changes to the development database and
retains its named volume. No workspace rows are inserted: an empty workspace
table is expected until the explicit Step 3.3 command below is run. Do not use test cleanup or
`alembic downgrade base` on this database. The downgrade is verified only in the
guarded disposable stack. No host Python or uv installation is required.

### Run the disposable PostgreSQL tests

From **Windows host PowerShell** in the project directory:

```powershell
.\scripts\check-backend.ps1
```

The checker supplies its own temporary settings file, unique Compose project,
network, and named PostgreSQL volume. It does not read the actual project `.env`
and does not use or reset the development database. The CI override keeps source
mounts and host ports absent; no database port or new service has been added.
The checker verifies real health/readiness, prepares the guarded test target,
applies migrations, prints and verifies the head revision, runs opted-in pytest,
initializes only the demo workspace twice, checks actual dependency outage/recovery,
and cleans up only its disposable stack.
GitHub CI performs the same migration/schema checks; frontend checks are retained.

Integration-test isolation is enforced before schema writes:

- `RUN_POSTGRES_TESTS=1` must be set explicitly on the test process.
- The target database and user must both be `supplier_invoice_verification_test`,
  with explicit credentials, host `db`, and port `5432`; there is no fallback.
- `POSTGRES_TEST_PROJECT` must match the checker's unique project name or the CI
  run/attempt name. PostgreSQL must confirm the expected database/user/version.
- A database comment must match that project. The preparation command can mark
  only a fresh empty database and refuses another marker or an unmarked database
  containing tables. Tests validate the marker before migrations, and again
  before their downgrade/upgrade lifecycle check.
- Individual tests use an outer transaction and savepoints so fixture rows and
  even explicitly committed test writes are rolled back after each test.

The suite checks model/migration agreement, table types, named constraints and
indexes, server defaults, valid relationships, rejected cross-workspace and
incompatible links, optional mapping pairs, identifier uniqueness, numeric/text/
date/currency/status rules, ORM reads/writes, and usable sessions after rollback.
It also proves repeatable upgrades and a disposable downgrade/upgrade round trip.

Ordinary pytest without opt-in runs the foundation/session/guard tests and skips
PostgreSQL integration tests with an explicit reason. To see those reasons on a
rebuilt development API image, run this **Windows host PowerShell command**, which
executes pytest inside the **Linux API container**:

```powershell
docker compose exec -T api pytest -q -rs
```

Use the disposable checker for the full schema suite; do not enable integration
tests on the development stack. See [progress](docs/progress.md) for checks already
performed and checks still awaiting user verification or online CI.

## Demo workspace and manual record APIs (Step 3.3)

Step 3.3 introduced create/list/retrieve supplier and purchase-order APIs.
[Step 3.4 below](#delivery-record-and-draft-invoice-apis-step-34) extends these
with delivery records and draft invoices. The existing status page and
health/readiness bodies are preserved.

### Explicit workspace initialization

From the project directory, use these **Windows host PowerShell commands**.
The `exec` commands run Python/Alembic inside the **Linux API container**:

```powershell
docker compose up --build -d
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
docker compose exec -T api python -m app.seed_workspace
docker compose exec -T api python -m app.seed_workspace
```

The command creates only workspace ID `00000000-0000-4000-8000-000000000001`,
slug `local-demo`, name `Local demo workspace`. Repeated execution preserves the
same row and timestamp. Conflicting ID, slug, or name causes a clear nonzero exit
without overwriting existing data. There are no startup/import writes and no
suppliers, orders, deliveries, or invoices seeded. The reusable helper lets a
later full demo seeder own its complete transaction.

Every business request uses that fixed workspace; clients cannot supply
`workspace_id` in bodies or query parameters. Reads, counts, filters, references,
and writes are workspace-scoped. A missing or conflicting demo workspace returns
generic HTTP 503. This is local demo context, not authentication or an access
boundary for real company data. Readiness continues to check connections even
when the workspace has not been initialized.

### Synthetic API verification

After initialization, run these **Windows host PowerShell commands** against the
local API. All data is fictional; quantities and prices stay JSON strings.

```powershell
$manualApiBase = 'http://127.0.0.1:8000'
$manualSupplierBody = @{
    supplier_code = 'DEMO-OFFICE-001'
    name = 'Demo Office Supplies'
    notes = 'Fictional supplier for local verification.'
} | ConvertTo-Json
$manualSupplier = Invoke-RestMethod -Method Post -Uri "$manualApiBase/suppliers" -ContentType 'application/json' -Body $manualSupplierBody

$manualOrderBody = @{
    supplier_id = $manualSupplier.id
    po_number = 'PO-DEMO-001'
    order_date = '2026-10-13'
    currency = 'EUR'
    lines = @(
        @{
            description = 'Keyboard'
            quantity = '10.000'
            unit_price = '25.0000'
        }
    )
} | ConvertTo-Json -Depth 4
$manualOrder = Invoke-RestMethod -Method Post -Uri "$manualApiBase/purchase-orders" -ContentType 'application/json' -Body $manualOrderBody

Invoke-RestMethod -Uri "$manualApiBase/suppliers?limit=20&offset=0" | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri "$manualApiBase/suppliers/$($manualSupplier.id)" | ConvertTo-Json
Invoke-RestMethod -Uri "$manualApiBase/purchase-orders?supplier_id=$($manualSupplier.id)&limit=20&offset=0" | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri "$manualApiBase/purchase-orders/$($manualOrder.id)" | ConvertTo-Json -Depth 6
```

Create returns HTTP 201 with a `Location` header such as
`/purchase-orders/{saved-id}`. Retrieve and list return HTTP 200. The example order
returns quantity `"10.000"`, unit price `"25.0000"`, line total `"250.00"`, and
subtotal `"250.00"`; its nested lines are ordered by server-assigned `line_no`.
Lists return `items`, `limit`, `offset`, and `total`; order list items omit lines.
See [the reviewed blueprint](docs/manual-workflow.md) for complete JSON shapes.

The commands create stored records, so running the same example again gives HTTP
409 for duplicate identifiers. Retrieve the existing records with the list/detail
endpoints, or use new fictional codes/numbers for another manual run. Workspace
initialization remains harmless to repeat independently of these record creates.

Lists default to 20 records and permit `limit=1..100`, `offset=0..10000`, sorted by
creation time descending and UUID descending for ties. Purchase orders optionally
filter by `supplier_id`; a valid absent or other-workspace supplier filter returns
an empty list. Unknown list parameters are rejected. Text is trimmed, required
text remains nonblank, and blank optional notes become null. Identifiers remain
case-sensitive. Orders require EUR, a valid `YYYY-MM-DD` date, and 1-100 lines.

Decimal requests accept only plain unsigned strings of 1-32 characters within
the blueprint's bounds: quantity has at most 3 fractional digits and must be
positive; price has at most 4 and may be zero. JSON numbers, whitespace, signs,
exponents, NaN/infinity, excess scale, and out-of-range values are rejected.
The backend uses Decimal with local precision 38 and `ROUND_HALF_UP` on each
line, then sums rounded cents. Two line products of `0.005` produce `0.01` each
and subtotal `0.02`. Calculated overflow is rejected before insertion; clients
cannot supply totals or other server-owned fields.

Headers and all lines commit together, once, before success is returned. A failed
save rolls back its entire document, including on a database uniqueness conflict.
The fixed error envelope contains only `error.code`, `error.message`, and an
array of `{field, message}` details: validation 422, missing record/reference 404,
identifier conflict 409, unavailable 503, and unexpected failure 500. Invalid
request values, unknown field names, SQL, connection strings, and raw exception
messages are not echoed in errors.

### Isolated verification

Use the existing **Windows host PowerShell** checker for the full suite:

```powershell
.\scripts\check-backend.ps1
```

Its approved disposable PostgreSQL target runs the new API/workspace tests along
with all foundation and schema tests. Each API request gets a fresh SQLAlchemy
session using a savepoint inside the test's outer transaction, so service commits
are real within the test but all synthetic data is removed afterward. Tests also
inject a real PostgreSQL line failure and a commit failure to prove whole-document
rollback, sanitized errors, and successful recovery. Initialization tests cover
repeat execution and conflicting data; the checker runs the actual module command
twice after pytest, before the retained HTTP outage/recovery checks and cleanup.

CI retains its existing triggers and adds pushes to `feat/manual-invoice-workflow`.
Frontend checks, migration guards, bounded waits, failure logs, read-only GitHub
permissions, and disposable cleanup remain. No applied migration was rewritten,
and no model/schema issue required a new migration for this checkpoint.

## Delivery-record and draft-invoice APIs (Step 3.4)

Both resources provide POST, GET list, and GET `/{id}` endpoints:
`/delivery-receipts` and `/invoices`. Creates return HTTP 201 with a relative
`Location` header and saved nested lines; retrieve returns the same full record.
Lists return header-only `items`, `limit`, `offset`, and workspace-scoped `total`.
The existing pagination limits and stable ordering apply. Delivery lists filter
by `purchase_order_id`; invoices filter by `supplier_id`, `purchase_order_id`,
or both together. A valid absent or other-workspace filter returns an empty list.

A receipt requires an existing order and 1-100 lines from that order, with one
entry per order line in each receipt. The server assigns line numbers and copies
the internal order ID. Multiple receipts and positive overdelivery quantities
are allowed; cumulative quantities are not compared in this checkpoint.

An invoice requires a supplier and may select one of that supplier's orders.
Each optional manual line mapping must refer to that selected order. Lines may
remain unmapped even with an order; an invoice without an order cannot have
mapped lines. Multiple invoice lines may map to the same order line. All invoices
are assigned `draft` by the server; client-supplied status is rejected, including
`draft`. There are no editing or deletion endpoints.

Invoice quantities/prices use the existing strict decimal-string rules. Required
`tax_amount` is an explicitly entered nonnegative amount, with at most two decimal
places and maximum `9999999999999999.99`. It is not a percentage or an inferred
tax amount. Each line is rounded HALF_UP to cents; rounded lines are summed for
`subtotal`, then tax is added for `total`. Responses format quantities to three,
prices to four, and monetary amounts to two decimal places. All calculated
overflows return 422 before insertion; supplied totals and internal line order
IDs are rejected. Optional `due_date` must be on or after `invoice_date`.

Missing or other-workspace references return 404. An existing line from another
order, an order from the wrong supplier, or an incompatible mapping returns 422.
Receipt numbers are unique per workspace; invoice numbers are unique per supplier
within the workspace. Database constraints handle duplicates, including races,
with 409 and rollback. Each header and all lines save in one transaction before
success is returned. Sanitized 422/404/409/503/500 responses use the existing
`error.code`, `error.message`, `error.details` envelope. Swagger now documents
that envelope for **all** business routes. Health/readiness contracts are unchanged.

### Synthetic delivery and invoice verification

Rebuild the API from **Windows host PowerShell** in the project directory:

```powershell
docker compose up --build -d api
```

The development database must already be migrated and the demo workspace
initialized as described above. No new migration or seeding is required for
Step 3.4 if Step 3.3 was verified. Open `http://127.0.0.1:8000/docs` to inspect
the new endpoints and business error schemas.

Use `$manualSupplier` and the full `$manualOrder` from the earlier fictional
supplier/order example. If those records already exist and the PowerShell session
was closed, retrieve them instead of posting duplicate creates (these commands
search the first 100 records; select another page if necessary):

```powershell
$manualApiBase = 'http://127.0.0.1:8000'
$manualSupplier = (Invoke-RestMethod -Uri "$manualApiBase/suppliers?limit=100").items | Where-Object supplier_code -EQ 'DEMO-OFFICE-001' | Select-Object -First 1
if ($null -eq $manualSupplier) { throw 'Create the fictional supplier using the earlier example first.' }
$manualOrderSummary = (Invoke-RestMethod -Uri "$manualApiBase/purchase-orders?supplier_id=$($manualSupplier.id)&limit=100").items | Where-Object po_number -EQ 'PO-DEMO-001' | Select-Object -First 1
if ($null -eq $manualOrderSummary) { throw 'Create the fictional order using the earlier example first.' }
$manualOrder = Invoke-RestMethod -Uri "$manualApiBase/purchase-orders/$($manualOrderSummary.id)"
```

Create a receipt for 8 of the 10 keyboards and an invoice charging for all 10.
These **Windows host PowerShell commands** write only fictional business records
when you explicitly run them:

```powershell
$manualReceiptBody = @{
    purchase_order_id = $manualOrder.id
    receipt_number = 'DR-DEMO-001'
    received_date = '2026-10-14'
    lines = @(
        @{
            purchase_order_line_id = $manualOrder.lines[0].id
            quantity_received = '8.000'
        }
    )
} | ConvertTo-Json -Depth 4
$manualReceipt = Invoke-RestMethod -Method Post -Uri "$manualApiBase/delivery-receipts" -ContentType 'application/json' -Body $manualReceiptBody

$manualInvoiceBody = @{
    supplier_id = $manualSupplier.id
    purchase_order_id = $manualOrder.id
    invoice_number = 'INV-DEMO-001'
    invoice_date = '2026-10-15'
    due_date = '2026-11-15'
    currency = 'EUR'
    tax_amount = '0.00'
    lines = @(
        @{
            description = 'Keyboard'
            quantity = '10.000'
            unit_price = '25.0000'
            purchase_order_line_id = $manualOrder.lines[0].id
        }
    )
} | ConvertTo-Json -Depth 4
$manualInvoice = Invoke-RestMethod -Method Post -Uri "$manualApiBase/invoices" -ContentType 'application/json' -Body $manualInvoiceBody

Invoke-RestMethod -Uri "$manualApiBase/delivery-receipts/$($manualReceipt.id)" | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "$manualApiBase/invoices/$($manualInvoice.id)" | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri "$manualApiBase/delivery-receipts?purchase_order_id=$($manualOrder.id)&limit=20&offset=0" | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri "$manualApiBase/invoices?supplier_id=$($manualSupplier.id)&purchase_order_id=$($manualOrder.id)&limit=20&offset=0" | ConvertTo-Json -Depth 4
```

Use the **header** `$manualOrder.id` for order URLs and header references; use
`$manualOrder.lines[0].id` only for line mappings. Expect received quantity
`"8.000"`, invoice quantity `"10.000"`, status `"draft"`, subtotal `"250.00"`,
tax `"0.00"`, and total `"250.00"`. The linked records show the 10/8/10 workflow;
automatic discrepancy detection remains deferred. For an invoice without an order,
omit or null both the header order ID and each line mapping. For an unmapped line
on a selected order, omit or null only `purchase_order_line_id`.

Repeating these creates returns 409. Retrieve existing records, or use new fictional
document numbers for another run. Authentication, uploads, AI, automatic matching,
approval, notifications, exports, and full demo seeding
remain later work.

### Isolated Step 3.4 checks

From **Windows host PowerShell**, run:

```powershell
.\scripts\check-backend.ps1
```

The existing checker and CI run all new PostgreSQL API tests automatically with
their explicit opt-in and disposable-database guards. The fixture uses a fresh
session per request inside an outer test transaction, so API commits, synthetic
rows, and failure-injection triggers are removed after each test. The suite checks
the complete workflow, optional mappings, workspace isolation, pagination,
decimal/tax/date rules, duplicate keys, and failure recovery. It injects actual
PostgreSQL second-line failures and pre-commit failures to prove atomicity.
Separate tests verify the published OpenAPI error contracts for every business
operation while preserving foundation contracts. Normal pytest still skips all
PostgreSQL tests unless the guarded disposable environment opts in. No host Python
installation or new dependency is needed. See [progress](docs/progress.md) for
completed checks and pending user/online CI verification.

## Supplier and purchase-order website (Step 3.5A)

Step 3.5A introduced Status, Suppliers, and Purchase orders navigation.
Step 3.5B adds Delivery records and Invoices, described below. Native hash links
support local deep links and browser history without
adding a routing dependency. An empty hash opens Status; unknown paths or invalid
page parameters show Page not found with a link to Status.

| Route | Page |
| --- | --- |
| `#/status` | Existing API/PostgreSQL/Redis checks and Refresh status. |
| `#/suppliers` | Paginated supplier codes and names, with creation/detail links. |
| `#/suppliers/new` | Supplier code, name, optional notes, Save and Cancel. |
| `#/suppliers/{id}` | Saved supplier fields and paginated linked purchase orders. |
| `#/purchase-orders` | Paginated order numbers, dates, EUR subtotals, and links. |
| `#/purchase-orders/new` | Paginated supplier chooser, header fields, and editable unsaved lines. |
| `#/purchase-orders/{id}` | Saved header, readable supplier link, ordered lines, and server subtotal. |

List hashes retain `limit` and `offset`, for example
`#/suppliers?limit=20&offset=20`. Order lists may also use `supplier_id`; supplier
details use their page parameters for linked orders. All pages observe the API's
limit of 1-100 records and maximum offset of 10000. Previous/Next controls and
counts show the current page. The supplier chooser fetches 20 records at a time
and retains the selection when moving between pages. If no supplier exists, it
explains that one must be created first and links to the creation form.

Business requests use native fetch and the existing `/api` development proxy.
Each request has a five-second bound covering headers and the complete response
body. Leaving a page or replacing a read cancels obsolete requests; completion
guards prevent stale results or a late save from redirecting a different page.
Validation, conflicts, missing records/references, service/server failures,
network failures, and timeouts are handled separately. Read failures offer Retry.

Forms use associated labels, hints, inline errors, a focusable error summary,
keyboard controls, and visible focus. They keep text/decimal values when a save
fails and focus the first invalid field when available. Save is guarded against
repeat submissions while active. Unsaved lines use stable local keys, with a
minimum of one and maximum of 100 lines. Add/remove controls apply only before
the document is saved. There are no saved-record editing/deletion controls.

Quantities and prices remain strings, including while entering JSON requests.
Unsigned decimal inputs reject whitespace, exponents, signs, JSON numbers, excess
scale, and values beyond the backend bounds. Required text is trimmed/nonblank;
blank optional notes become null. The date is a calendar-date string without a
timezone conversion. The website performs no financial multiplication, rounding,
or subtotal calculation. It displays the exact strings returned by the backend.

Drafts and save-error feedback stay in React memory across navigation in the same
tab. They are cleared on successful creation or a full reload, and are never
written to browser storage. Cancel returns to the list and retains the unsaved
draft for this session. Interrupted, timed-out, or lost save responses may mean
the record was already saved. The form preserves its input and offers **Check
saved records (opens a new tab)** to find the code/number before another Save.
Conflicts offer the same list check. POST requests are never automatically retried.

### Start the website and run checks

Using your existing local backend setup, run these **Windows host PowerShell
commands** from the project directory. No host Python or new npm dependency is
required; the existing Node.js 24 setup and lockfile remain in use:

```powershell
Set-Location frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Keep the Vite terminal running while checking pages.
The `/api` proxy applies to development; production hosting/API routing is outside
this checkpoint.

### Manual browser verification still to perform

Use existing fictional records for read-only navigation checks. Exercise creation
in your chosen synthetic verification stack: Save creates PostgreSQL records in
the database served by that API. No development record writes or browser checks
were performed during Step 3.5A implementation.

1. Open the site without a hash, then `#/status`. Verify the three checks, refresh
   disabling, and failure/recovery after an outage in the synthetic test stack.
2. Follow Suppliers and Purchase orders, use Back/Forward, paste detail deep links,
   and reload those URLs. Check an unknown route and a valid absent record UUID.
3. Verify empty/loading/error states, Retry, list page counts, Previous/Next,
   supplier details' linked order pages, and order-to-supplier navigation.
4. In Create supplier, enter only fictional code/name/notes. Check blank/oversized
   fields and duplicate-code feedback. Save valid data and confirm navigation uses
   the returned supplier header ID. Verify trimmed text and nullable notes.
5. In Create purchase order, browse supplier pages beyond the first and select a
   readable code/name. Confirm selection survives paging. With no suppliers,
   confirm the create-first explanation/link.
6. Enter a fictional number/date and one Keyboard line with quantity `10.000`
   and price `25.0000`. Add/remove unsaved lines, check required/decimal/date/line
   limits, and save. Expect the detail view's saved subtotal `250.00` EUR; quantities
   and prices should retain their backend fixed scales.
7. Check keyboard tab order, radio selection, labels, first-error focus, error
   summary, visible focus, and table scrolling/layout at narrow widths. Try repeat
   Save clicks and confirm one document request. Verify typed input survives failure.
8. Simulate a delayed/lost POST response using browser network tools in the test
   stack. Check the uncertain-save message, retained input, list check before a
   manual retry, and absence of automatic POST retries. Leave during a save and
   confirm a late response does not redirect the new page; return to inspect the
   retained draft and warning. Also leave a delayed read and verify no stale page.

The Node tests use simulated responses and pure navigation/validation/request
helpers; they do not establish that these real browser workflows passed.
See [progress](docs/progress.md) for the actual automated results and remaining
browser/online CI verification.

## Delivery-record and draft-invoice website (Step 3.5B)

Navigation retains **Supplier-Invoice-Verification**, Status, Suppliers, and
Purchase orders, and adds Delivery records and Invoices. The website uses the
existing React/TypeScript, native fetch, CSS, hash links, and `/api` Vite proxy;
no new dependency is needed. Website `#/deliveries` calls backend
`/api/delivery-receipts`, not `/api/deliveries`.

| Route | Page |
| --- | --- |
| `#/deliveries` | Paginated receipt numbers/dates, detail links, and order links. |
| `#/deliveries/new` | Paginated order choice, receipt number/date/notes, descriptive line choices, and received quantities. |
| `#/deliveries/{id}` | Saved receipt fields/quantities, order-line descriptions, and linked order/supplier. |
| `#/invoices` | Paginated invoice numbers/dates, draft status, and EUR totals. |
| `#/invoices/new` | Supplier, optional filtered order, dates, explicit tax, notes, and priced lines with optional manual mappings. |
| `#/invoices/{id}` | Saved draft fields/lines, supplier/optional-order links, subtotal, tax, and total. |

Delivery list hashes may filter by `purchase_order_id`; invoice hashes may filter
by `supplier_id`, `purchase_order_id`, or both together. `limit` and `offset` use
the same bounds as the existing pages. Paging preserves filters. Order details
now contain separate paginated delivery and invoice sections, and supplier details
contain a paginated invoice section. Each section has its own request, retry,
loading/error state, and page controls, so one failed related read does not hide
the other saved records. Related sections start on their first page after reload.

### Delivery entry

Choose an order by its readable number/date; Previous/Next browse orders in pages
of 20. The form fetches that selected order's lines and displays their descriptions
with checkboxes. Choose at least one line and enter each received quantity as a
positive decimal string. A checkbox permits only one entry for an order line in
the receipt. Changing the order clears the prior line selections immediately.
Obsolete order-detail results are cancelled/ignored and cannot restore old choices.
Multiple receipts for an order are allowed, including positive quantities above
ordered quantities; no cumulative comparison or discrepancy detection is added.

Saved receipt responses contain received quantities and line references; the
detail view retrieves the order separately for descriptions and supplier links.
If that related lookup fails, receipt fields and quantities remain visible with
their order links and an independent Retry action.

### Draft invoice entry

Choose a supplier by code/name, using the existing paginated chooser. The optional
order chooser lists only that supplier's orders, also in pages of 20. Select
**No purchase order** to save without one. Enter number/date, optional due date,
fixed EUR currency, optional notes, and an explicit nonnegative invoice-level
`tax_amount`. Tax starts blank; enter `0.00` if there is no tax. It is an amount,
not a percentage or an inferred tax calculation.

Priced lines keep descriptions, quantities, and prices as entered strings.
With an order selected and its current details loaded, each line may use a
descriptive manual mapping or remain **Unmapped**. No order means all mappings
must be empty. Changing supplier clears the order and all mappings; changing
order clears mappings. Other typed values and stable unsaved line keys remain.
Old supplier/order results cannot populate the current choices. Selection of an
order line does not copy prices, descriptions, or quantities into invoice lines.

The server assigns `draft`, calculates each rounded line total and subtotal, then
adds the entered tax. The website displays the returned decimal strings and never
performs authoritative financial calculations. Requests omit status, totals,
local keys, workspace fields, and internal line order IDs. Required text/date,
decimal bounds/scales, due-date ordering, 1-100 lines, duplicate receipt choices,
and selected-order ownership/membership are validated before save; backend
validation remains authoritative.

Both new forms reuse disabled/guarded saving, field labels, inline errors, summary,
focus behavior, keyboard controls, full-body five-second requests, and cancellation.
Input and error feedback remain in memory across navigation in the same tab.
Interrupted/network/timed-out save responses may mean a document was saved: check
the linked list in a new tab for its number before a manual retry. POST requests
are never automatically retried. Successful creation clears the corresponding
draft and navigates using the returned top-level document ID. Full reload clears
unsaved drafts; saved deep links retrieve records from the API.

### Checks and remaining browser verification

From **Windows host PowerShell** in the project directory:

```powershell
Set-Location frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Use existing fictional records for read-only checks.
Exercise creation only in your chosen synthetic verification stack; Save writes
records to the database served by that API. No development writes or actual
browser checks were performed during Step 3.5B implementation.

1. Check all five navigation links, empty-hash Status, unknown routes, Back/Forward,
   refresh, list/filter URLs, and saved delivery/invoice deep links.
2. For the existing fictional 10-keyboard order at EUR 25, create a delivery of
   `8.000` against the descriptive Keyboard checkbox. Change orders during delayed
   detail loading and confirm old lines/quantities are cleared and do not reappear.
3. Create a draft invoice for `10.000` keyboards at `25.0000`, with tax `0.00`.
   Confirm saved subtotal/total `250.00`, received quantity `8.000`, draft status,
   links, and independently paginated related records. No discrepancy flags should appear.
4. Exercise supplier/order choices beyond page one, empty selectors, no-order
   invoices, selected-order invoices with unmapped lines, mixed/manual mappings,
   and supplier/order changes clearing dependencies while preserving other input.
5. Check invalid decimals/dates/early due dates, omitted tax, duplicate numbers,
   missing references, server/network/timeouts, retained input, error summary and
   first-error focus. Verify labels, keyboard controls, visible focus, and narrow layouts.
6. Delay/fail one related list and confirm the other sections remain usable. Leave
   during a read or save and verify obsolete responses do not update/redirect the
   new page. Check uncertain-save feedback/list lookup before retrying and confirm
   repeat Save clicks do not issue multiple POSTs.

The Node tests cover synthetic contracts, dependent selections, payloads, decimals,
filters, errors, cancellation, and uncertain writes using mocks/helpers. They do
not prove these real browser workflows or saved-record persistence through the
website. The automated outcomes and pending browser/online CI checks are recorded
separately in [progress](docs/progress.md). Seeding, saved-record editing/deletion,
authentication, uploads, AI, matching, approval, exports, and cloud deployment
remain later milestones.
