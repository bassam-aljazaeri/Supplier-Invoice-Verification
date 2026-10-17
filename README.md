# Supplier-Invoice-Verification

AI-assisted supplier invoice extraction, matching, review, and approval.

## Status
The local website has Status, supplier, purchase-order, delivery-record, and
draft-invoice pages backed by PostgreSQL. Step 3.6 adds an explicit repeatable
fictional demo and disposable persistence verification. This milestone is a
local manual-record application. Extraction, automatic discrepancy detection,
and approval remain later work.

Step 4.4 protects all business APIs with Cognito access-token verification and
database workspace permissions. Identity, workspace, and membership APIs are
available. **The existing frontend needs Step 4.5 login integration before it
can access business records.** Its public Status page still works. See
[the current authentication instructions](#backend-authentication-and-authorization-step-44).
The older Step 3 examples below describe business payloads; their requests now
also require the authentication and workspace headers documented there.

For setup and the 10 ordered / 8 delivered / 10 invoiced demonstration, see
[the demo guide](docs/demo.md) and [the seed instructions below](#repeatable-fictional-demo-step-36).

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
complete JSON results. After pytest, the backend job initializes the demo
workspace twice and runs the full demo seed twice. The shared demo checker reads
all four documents and their lines through live HTTP, checks filtered lists and
Swagger examples, and compares IDs, timestamps, values, and counts. It retains
that snapshot, restarts API and PostgreSQL without removing the database volume,
waits for recovery, and retrieves the same records to prove persistence.
It then stops its PostgreSQL and Redis containers, checks that `/health` remains HTTP 200 while `/ready` reports
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

Expect revision `0002_auth_workspaces (head)` after Step 4.3. Running `upgrade head` again is
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
initializes the workspace twice, seeds the complete demo twice, and proves its
live API records survive an API/PostgreSQL restart with the volume retained.
It checks actual dependency outage/recovery and cleans up only its disposable stack.
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
suppliers, orders, deliveries, or invoices seeded by this command. The reusable
noncommitting helper is also used by Step 3.6's whole-demo transaction.

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
document numbers for another run. Step 3.6 adds a separate repeatable fixture
command; ordinary API creates still return 409 for duplicate identifiers.
Authentication, uploads, AI, automatic matching, approval, notifications, and
exports remain later work.

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
separately in [progress](docs/progress.md). Saved-record editing/deletion,
authentication, uploads, AI, matching, approval, exports, and cloud deployment
remain later milestones.

## Repeatable fictional demo (Step 3.6)

Start with Docker Desktop running Linux containers and existing local database
settings configured as in the foundation setup. From the project directory, use
these **Windows host PowerShell commands**. Alembic and Python execute inside
the **Linux API container**; host Python or uv is not required.

```powershell
docker compose up --build -d
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
docker compose exec -T api python -m app.seed_demo
docker compose exec -T api python -m app.seed_demo
```

Expect `0002_auth_workspaces (head)` and a successful fictional-demo summary on
each seed. The seed initializes the fixed workspace if missing; a separate
`seed_workspace` run is optional. These commands intentionally write your chosen
local demo database. Codex ran seeding only in the guarded disposable checker,
never against the development database.

Open a second **Windows host PowerShell** terminal in the project directory:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://127.0.0.1:5173/#/status`, then follow [the browser demonstration](docs/demo.md).
Stop Vite before `npm ci` if it is already running. The documented fixed IDs are
for this fixture; ordinary forms continue to use returned server IDs.

| Record | Fixed ID | Expected data |
| --- | --- | --- |
| Workspace | `00000000-0000-4000-8000-000000000001` | `local-demo`, Local demo workspace |
| Supplier | `10000000-0000-4000-8000-000000000001` | DEMO-OFFICE-001, Demo Office Supplies |
| Purchase order | `20000000-0000-4000-8000-000000000001` | PO-DEMO-001, 2026-10-13, 10 keyboards at EUR 25, subtotal 250.00 |
| Order line | `21000000-0000-4000-8000-000000000001` | Keyboard, quantity 10.000, unit price 25.0000 |
| Delivery receipt | `30000000-0000-4000-8000-000000000001` | DR-DEMO-001, 2026-10-14, 8.000 received |
| Receipt line | `31000000-0000-4000-8000-000000000001` | References the fixed order line |
| Invoice | `40000000-0000-4000-8000-000000000001` | INV-DEMO-001, 2026-10-15, due 2026-11-14, draft, subtotal/total 250.00, tax 0.00 |
| Invoice line | `41000000-0000-4000-8000-000000000001` | Keyboard, quantity 10.000, unit price 25.0000, manual mapping to the fixed order line |

The fixture matches the reviewed blueprint, including supplier notes and optional
invoice due date. It uses the same create schemas, scoped reference validation,
and Decimal calculations as API requests. All eight records are inserted or
verified in one transaction. No import or API startup runs the seed.

Repeating a successful seed preserves IDs, timestamps, values, lines, and counts.
Missing expected records are inserted. Existing demo rows must match every
expected business field and the exact fixed IDs; unexpected document lines also
conflict. An occupied fixed ID or scoped identifier, conflicting workspace, or
database failure exits nonzero and rolls back all inserts without overwriting
anything. Errors do not print existing private values or connection details.
Unrelated `MANUAL-*`, `UI-*`, and other-workspace records remain unchanged.

If earlier manual/Swagger creates already used `DEMO-OFFICE-001`, `PO-DEMO-001`,
`DR-DEMO-001`, or the supplier-scoped `INV-DEMO-001` with generated IDs, they
conflict even when their visible fields look identical. The seed never adopts or
renames them. Keep them for manual browsing, inspect the conflict, and use a
separately chosen fresh demo database if the fixed fixture is needed; do not
reset or delete development data to make seeding pass. Reserve the fixed demo
identifiers for this command and use `MANUAL-*` or `UI-*` for additional examples.

### Final disposable verification

From **Windows host PowerShell**, without stopping the development stack:

```powershell
.\scripts\check-backend.ps1
```

The script uses generated settings and a unique disposable project with no host
ports/source mounts. PostgreSQL tests and the shared demo checker require explicit
opt-in, the approved database/user/host/version, and that project's database
marker before connecting to or seeding a test target. There is no development
fallback. The checker captures actual returned header/line IDs and decimal values,
seeds twice, then compares the full live API snapshot after container restart.
Recovery has a bounded 60-second wait; containers are restarted with their named
volume intact. Final cleanup removes only the disposable project's resources.
GitHub backend CI runs the same `scripts.check_demo` checks and retains the
existing health/readiness/outage/recovery checks and frontend job.

The automated repeatability/persistence checks use real PostgreSQL and live HTTP.
They do not exercise website rendering or browser interactions. Use the demo guide
for those checks, and record browser and online GitHub results separately in
[progress](docs/progress.md). Step 3.6 itself needed no new migration or dependency;
Step 4.3 adds the following persistence migration.

## User and membership persistence (Step 4.3)

This checkpoint adds `application_users` and `workspace_memberships`, revision
`0002_auth_workspaces`, internal persistence services, and an explicit local
operator command. This section records the persistence checkpoint. Step 4.4
now enforces those roles on protected routes and adds `/me`, workspace, and
membership APIs. Frontend login, approval actions, and additional AWS resources
remain outside these checkpoints.

Users have a server UUID, the exact case-sensitive `(issuer, subject)` identity,
active status, and creation/update timestamps. No email, password, or token is
stored. Memberships reference an existing workspace and user with restrictive
foreign keys, a unique workspace/user pair, and exactly one of `administrator`,
`accountant`, or `approver`. Named constraints and indexes are checked against
PostgreSQL. The new migration inserts no rows and changes no existing workspace
or business record. The applied `0001_manual_records` is unchanged.

### Required operator configuration

No Cognito configuration was present before this step. The tracked `.env.example`
now documents placeholders for `COGNITO_REGION` and `COGNITO_USER_POOL_ID`, and
Compose passes them to the API container. Step 4.4 additionally requires
`COGNITO_APP_CLIENT_ID` for API startup; there is no unauthenticated fallback.
The operator command refuses missing, malformed, or mismatched region/pool values
before opening a database session. No actual environment file is supplied or
changed by this implementation. You can set the two values in your current
PowerShell process instead of editing a file.

Use the region and matching pool ID of the intended existing Cognito user pool.
The issuer is derived as
`https://cognito-idp.{region}.amazonaws.com/{user_pool_id}` (China uses
`amazonaws.com.cn`). This supports the original regional issuer profile; updated
or multi-region issuer profiles need a later reviewed configuration contract.
There is no `--issuer` override, AWS key, client secret, browser setting, discovery
request, or AWS call. See [Cognito's issuer/token documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html).

Copy the intended person's exact `sub` from the selected pool through a trusted
operator channel, such as that user's Cognito record. It is not their email or
username. The command deliberately trusts the local operator's supplied subject;
it does not confirm an AWS account exists, decode a pasted token, or require
prior application login. If you do not yet have an intended pool and subject,
leave the operator command for later. Disposable tests need neither.

### Build, migrate, and grant deliberately

These are **Windows host PowerShell commands** from the project root for a
later user-run update of the chosen local database. Python and Alembic execute
inside the **Linux API container**. Replace all uppercase placeholders
with the intended pool's values before running. The build/recreate is necessary
to load Compose settings and the migration packaged in the image; it retains
PostgreSQL's existing volume. Codex has not run these against development.

```powershell
$env:COGNITO_REGION = 'YOUR_REGION'
$env:COGNITO_USER_POOL_ID = 'YOUR_USER_POOL_ID'
$env:COGNITO_APP_CLIENT_ID = 'YOUR_PUBLIC_APP_CLIENT_ID'
docker compose up --build -d api
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
docker compose exec -T api python -m app.bootstrap_membership --subject 'COPIED_COGNITO_SUB' --workspace-slug local-demo --role administrator
```

Expect `0002_auth_workspaces (head)` and a `Membership ready` result containing
the application-user UUID, workspace UUID, and role. No subject, credentials,
token, or connection string is printed. Existing records stay in `local-demo`
with their current IDs and values. No reset, destructive downgrade, or volume
removal is needed.

The workspace must already exist. If this is a fresh local setup where it has
not been initialized, explicitly run this **Windows host PowerShell command**
(Python runs in the **Linux API container**), then repeat the grant above:

```powershell
docker compose exec -T api python -m app.seed_workspace
```

Do not rerun initialization to repair an ID/slug/name conflict; its existing
insert-or-verify rules still refuse overwriting. Bootstrap itself never seeds,
creates, renames, or substitutes a workspace. You may explicitly select another
existing workspace slug; its IDs also stay unchanged.

To prove a harmless repeat, use the same subject, workspace, and role again from
**Windows host PowerShell** (Python runs in the **Linux API container**):

```powershell
docker compose exec -T api python -m app.bootstrap_membership --subject 'COPIED_COGNITO_SUB' --workspace-slug local-demo --role administrator
```

The first successful grant creates the application user if needed and adds the
membership. A repeat preserves both IDs and timestamps. A different existing
role exits nonzero instead of silently replacing it. Missing workspace, inactive
user, invalid input/configuration, or database failure also exits nonzero, with
no partial identity or grant. It never reactivates a disabled user. The command
may explicitly add other users/roles, but has no HTTP endpoint and never runs
through import, startup, migrations, `seed_workspace`, or `seed_demo`.

### Service transactions and concurrent role changes

`services.identity.ensure_application_user` and the functions in
`services.memberships` never commit or roll back. Their caller owns one
transaction and must commit success or roll back failure. The CLI's
`bootstrap_membership` wrapper owns that boundary; its `ensure_bootstrap_membership`
helper can participate in another caller's transaction. Step 4.4 membership
routes authenticate and recheck administrator authority after obtaining the
workspace lock, then reuse the same services and transaction.

All membership additions, role changes, and removals lock the existing workspace
row with `SELECT ... FOR UPDATE`, then lock/reread the target user and membership.
That row lock makes competing changes wait for each other. READ COMMITTED makes
the query after waiting see the other transaction's committed result. Services
require that isolation level and hold locks until the caller commits or rolls
back. The last active administrator cannot be removed or demoted; an
administrator in another workspace or an inactive user does not count. A no-op
role change preserves `updated_at`; a real change updates it. Lock waiting is
bounded at three seconds and an error requires rollback before recovery.
Established permissions must be changed through this protocol; direct SQL can
bypass service rules. No user deactivation/removal tool is introduced here.

### Isolated checks

From **Windows host PowerShell**, run:

```powershell
.\scripts\check-backend.ps1
```

The retained checker builds the locked image and runs Alembic/pytest inside
**Linux containers** using generated disposable settings and its own guarded
PostgreSQL database/volume. It does not read the actual project environment file
or migrate development. New tests use synthetic Cognito settings and no AWS
calls. Most rows roll back through the existing savepoint fixtures; concurrency
and real module-command tests commit only known synthetic rows and delete only
their own IDs after repeating the connected disposable marker guard.

Checks cover fresh schema/metadata agreement, populated `0001` upgrade without
changing existing records, identity uniqueness including concurrent registration,
relationships/FKs, role validation, bootstrap repeat/conflict/missing workspace,
atomic rollback and recovery, competing administrator changes on independent
connections, and lock timeout/recovery. Existing seeding, live HTTP persistence
across restart, dependency outage/recovery, and disposable cleanup remain in the
same checker. CI already discovers the new tests; no workflow change or AWS
account/credentials are required. Exact outcomes and remaining verification are
recorded in [progress](docs/progress.md).

Local Step 4.3 validation on 2026-10-17 passed: 593 backend tests with PostgreSQL
opt-in and no skips, plus the live repeated-seed, restart-persistence,
dependency-outage/recovery, and disposable cleanup checks. A separate image run
with Docker networking disabled passed 162 tests and skipped 431 integration
tests with the explicit opt-in reason. Both runs reported the existing
Starlette/httpx deprecation warning. These local results are not an online
GitHub CI result; frontend checks were not rerun because frontend files did not
change.

## Backend authentication and authorization (Step 4.4)

Every supplier, purchase-order, delivery-receipt, and invoice operation now
requires a verified Cognito access token and a current PostgreSQL membership.
The backend identifies a person by the exact verified `(issuer, sub)` pair;
email, groups, role headers, and browser controls do not grant authority.
Administrators/accountants create business records; all three roles read them.
Only administrators manage memberships. Approval actions remain deferred.

The schema is still `0002_auth_workspaces`. No new migration or destructive
reset is needed for Step 4.4; existing data and memberships remain in place.
`app.bootstrap_membership` remains an explicit operator command, never a public
endpoint or startup action. Fresh authenticated users get their own application
ID through `/me`, without automatic access to `local-demo` or another workspace.

### Required configuration and startup

Use the existing intended Cognito user pool and a public browser app client
without a client secret. This change creates no AWS resources. The three public
backend settings are:

| Setting | Purpose |
| --- | --- |
| `COGNITO_REGION` | Pool region. |
| `COGNITO_USER_POOL_ID` | Region-prefixed pool ID; derives the trusted original regional issuer and its `/.well-known/jwks.json` URL. |
| `COGNITO_APP_CLIENT_ID` | Public app client ID; must match the access token's `client_id`. |

The tracked `.env.example` contains placeholders only. Actual local environment
files were not inspected or changed. You can configure a PowerShell process
without writing a file. Replace the placeholders, then run these **Windows host
PowerShell commands** for a later deliberate development API update:

```powershell
$env:COGNITO_REGION = 'YOUR_REGION'
$env:COGNITO_USER_POOL_ID = 'YOUR_USER_POOL_ID'
$env:COGNITO_APP_CLIENT_ID = 'YOUR_PUBLIC_APP_CLIENT_ID'
docker compose up --build -d api
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/ready'
```

Startup validates all three settings without contacting Cognito or writing to
PostgreSQL. Missing/malformed values prevent API startup rather than expose
unprotected business routes. Once configured, `/health` and `/ready` stay public
with their original bodies and dependency behavior; public `/docs` and
`/openapi.json` expose schema only. No AWS IAM key, client secret, signing key
file, arbitrary JWKS URL setting, auth-disable switch, or demo bypass is used.
Loopback host-port binding and the existing PostgreSQL volume are unchanged.

Do not run migrations or seed commands merely to repair an authentication
failure. The user's existing Step 4.3 development migration and bootstrap were
recorded complete; Codex did not inspect or alter development data in Step 4.4.
For a genuinely fresh setup, use the earlier explicit migration/workspace/seed
commands against the deliberately chosen database, retaining its volume.

### Verify a real access token manually when available

Step 4.5 will implement browser Authorization Code Flow with PKCE. Until then,
use an access token obtained through the intended Cognito app client's existing
authorized flow, or use the fully synthetic checker below. This repository
provides no application endpoint that mints tokens. An ID token is not an API
credential. Real Cognito login has not been verified by the automated tests.

These **Windows host PowerShell commands** prompt without echoing the token and
keep it in process memory; do not store it in a file or add it to Git:

```powershell
$authSecureToken = Read-Host 'Cognito access token' -AsSecureString
$authHeaders = @{ Authorization = 'Bearer ' + ([System.Net.NetworkCredential]::new('', $authSecureToken).Password) }
$authMe = Invoke-RestMethod 'http://127.0.0.1:8000/me' -Headers $authHeaders
$authMe.user
$authMe.memberships | Select-Object workspace_id, role
Invoke-RestMethod 'http://127.0.0.1:8000/workspaces' -Headers $authHeaders
```

`/me` registers a missing verified application identity and returns `user` plus
the caller's own `memberships`. With no memberships, use the returned own UUID
to request access from an administrator, deliberately bootstrap through the
existing local operator command, or create a workspace. Other protected APIs
require this initial `/me` registration. The operator command still requires
the trusted pool's copied subject and must not use an unverified token decode.

Workspace creation needs no selected-workspace header. From **Windows host
PowerShell**, with the in-memory bearer headers above:

```powershell
$authWorkspacePayload = @{ slug = 'fictional-team'; name = 'Fictional team' } | ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8000/workspaces' -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $authWorkspacePayload
```

It returns 201 only after the workspace and caller's first administrator
membership commit together. Slugs use lowercase letters/digits with single
hyphens, maximum 64 characters; `local-demo` is reserved. A lost write response
must be checked against the caller's workspace list before a manual retry.

Business requests require exactly one `X-Workspace-ID` chosen from current
accessible workspaces. This is an untrusted selection; the server verifies
membership for every request. From **Windows host PowerShell**:

```powershell
$authBusinessHeaders = $authHeaders.Clone()
$authBusinessHeaders['X-Workspace-ID'] = 'COPY_ACCESSIBLE_WORKSPACE_UUID'
Invoke-RestMethod 'http://127.0.0.1:8000/suppliers' -Headers $authBusinessHeaders
Remove-Variable authSecureToken, authHeaders, authBusinessHeaders
```

Do not send `X-Workspace-ID` on `/me`, `/workspaces`, or membership-management
routes. Membership routes use only their path workspace ID. Backend paths omit
`/api`; the existing Vite proxy adds/removes that prefix for browser requests.

| Membership API | Contract |
| --- | --- |
| `GET /workspaces/{workspace_id}/memberships` | Administrator-only paginated list. |
| `POST /workspaces/{workspace_id}/memberships` | Existing active `application_user_id` and exact `role`; 201 after commit. No email lookup or invitation. Duplicate membership is 409. |
| `PATCH /workspaces/{workspace_id}/memberships/{application_user_id}` | Only `role`; 200, with harmless same-role assignment. |
| `DELETE /workspaces/{workspace_id}/memberships/{application_user_id}` | 204 after commit; removing/demoting the last active administrator is 409. |

List defaults/ranges remain limit 20 (1-100), offset 0 (0-10000). Workspace
discovery and its counts include only caller memberships. Membership changes
take the workspace lock and reread caller authority after waiting, so a removed
or demoted administrator cannot act using a stale dependency result.

### Verification and failure behavior

PyJWT with cryptography verifies real RS256 signatures, exact issuer, required
subject/time claims, `token_use=access`, and matching app client ID. The reviewed
unbound Cognito access-token profile rejects any `aud` claim; resource-bound
tokens need a later explicit audience contract. ID/unsigned/forged tokens and
other algorithms are rejected. Token-provided key URLs are never followed.

Trusted public keys are cached for five minutes. Refreshes, including unknown
key handling, are limited to once per 30 seconds per process. Fetches have a
three-second total deadline covering lock wait and the full response, a 64 KiB
body cap, and no redirects or environment proxy configuration. Known keys in a
valid cache may verify during outage; expired keys are never a fallback.

Errors retain `error.code`, `error.message`, and `error.details`. Missing/invalid
credentials are 401 with `WWW-Authenticate: Bearer`; denied membership/role or
inactive identity is 403. Missing/malformed/duplicate workspace selection is
422. Records/references outside an authorized workspace are 404, while selecting
an inaccessible/nonexistent workspace is an indistinguishable 403. An unknown
key after a successful JWKS refresh is 401; required signing-key retrieval or
database unavailability is sanitized 503. Tokens, SQL, and internal exception
details are not returned or logged. Protected responses use `no-store`; Uvicorn
access logs are disabled to avoid recording sensitive query strings.

Roles and local active status are reread from PostgreSQL on every request, so
committed removals/demotions affect the next request with the same unexpired
token. Logout alone does not immediately invalidate an issued JWT to an offline
signature verifier; local membership removal/deactivation is the immediate
application denial mechanism. No deactivation HTTP API is added here.

### Isolated authenticated verification

From **Windows host PowerShell**, run:

```powershell
.\scripts\check-backend.ps1
```

Alembic/pytest and real HTTP checks execute inside **Linux containers**. The
retained guards require a unique disposable Compose project, explicit test
database/user, PostgreSQL 17, and the connected project marker before writes.
No actual local environment file, live AWS account, credentials, or user token
is required. Only generated synthetic disposable settings are used and removed.

The CI override alone launches `tests.run_http_api`, a separate guarded
entrypoint. It generates a temporary RSA key inside that disposable API
container; the real verifier receives only its public JWKS through an injected
test key source. The private key stays in a restricted `/tmp` directory and
signs fresh short-lived synthetic tokens for checker processes. Keys survive
the same container's restart, then disappear when it is removed. Unit tests also
exercise the production HTTPS transport using controlled responses. No test
replaces signature verification or database authorization with a blanket mock.

After migrations and pytest, the checker explicitly initializes the workspace,
registers the signed synthetic user through `/me`, runs the operator bootstrap,
and seeds twice. Authenticated detail/list/filter snapshots must match after
API/PostgreSQL restart with volume retained. Actual HTTP checks also reject an
absent token, a forged signature, and a non-member, and prove scoped 404s. Public
health/readiness checks remain unauthenticated before migrations and throughout
dependency outage/recovery. All disposable containers, volumes, and key artifacts
are cleaned up even on failure. CI adds the `feat/auth-workspaces` push branch
and retains the unchanged frontend job and read-only permissions.

The existing frontend business pages cannot yet attach the required credentials
or workspace selection. Step 4.5 is required before using those pages; Status
remains available. Real Cognito/browser and online CI results must be recorded
separately from local generated-key verification in [progress](docs/progress.md).

Local Step 4.4 verification on 2026-10-17 passed: **684 backend tests** with
guarded PostgreSQL, authenticated HTTP denial/scoping checks, repeated seeding,
unchanged snapshots after API/PostgreSQL restart, public outage/recovery, and
disposable cleanup. Offline backend pytest passed **222 tests** with 462 explicit
PostgreSQL opt-in skips. Unchanged frontend checks passed **140 tests**, lint,
and production build; local actionlint and PowerShell syntax checks passed.
The existing Starlette TestClient/httpx deprecation warning remains. No real
Cognito/browser login or online GitHub Actions run was observed.
