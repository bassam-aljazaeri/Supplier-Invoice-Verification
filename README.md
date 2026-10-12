# Supplier-Invoice-Verification

AI-assisted supplier invoice extraction, matching, review, and approval.

## Status
Local development status page is available. Invoice application features are
not implemented yet. Step 3.2 adds the PostgreSQL schema, migrations, and session
management; business APIs, forms, calculations, and demo seeding remain later work.

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
to `main` or `feat/local-foundation`. Both jobs use GitHub-hosted Ubuntu 24.04
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
complete JSON results. After pytest, the backend job stops its PostgreSQL and
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
Line-count limits, decimal-string API validation, rounding, and document subtotal
calculation belong to later business schemas/services; PostgreSQL itself coerces
input to a numeric column's scale. This step does not calculate line totals.

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
table is expected until a later seeding checkpoint. Do not use test cleanup or
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
checks actual dependency outage/recovery, and cleans up only its disposable stack.
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
performed and checks still awaiting the user's development migration or online CI.
