# Progress

Current milestone: 3 - Manual business records
Current task: Step 3.6 - repeatable demo data and final verification

Milestone 2: Completed. The validation records below are retained as historical
evidence; Step 3.1 does not claim a new CI run or pull-request merge.

Completed:
- Defined the first-release scope
- Added project documentation and ignore rules
- Added the FastAPI health and dependency readiness endpoints
- Added the Docker Compose API, PostgreSQL, and Redis development stack
- Added backend dependency lockfile, startup instructions, and endpoint tests
- Replaced the frontend starter page with live API and dependency status checks
- Configured the Vite local server and `/api` proxy to the FastAPI host port
- Documented frontend startup and the proxy request path
- Added full-response timeouts, cancellation, independent status updates, and recovery checks
- Added the Step 2C workflow with separate frontend and disposable Compose backend jobs
- Added real HTTP health/readiness, dependency outage, and recovery checks
- Added a PowerShell command to reproduce the disposable backend checks locally
- Completed Milestone 2 - Local foundation
- Reviewed the Step 3.1 manual-workflow blueprint as the implementation contract
- Completed Step 3.2 database/session foundation and disposable PostgreSQL schema verification
- Completed Step 3.3 explicit workspace initialization, supplier/purchase-order APIs, and isolated API verification
- Completed Step 3.4 delivery-record and draft-invoice APIs, business OpenAPI error contracts, and isolated API verification
- Completed Step 3.5A website navigation, supplier/purchase-order pages, and frontend helper verification
- Completed Step 3.5B delivery-record/draft-invoice website pages, connected details, and frontend helper verification

Earlier Step 2A checks (recorded previously; not rerun for Step 2B):
- `docker compose config --quiet` passed
- Docker image built successfully with Python 3.12 and the locked dependencies
- `docker compose exec -T api pytest -q` passed (4 tests)

Step 2B checks (2026-10-06; Windows host PowerShell):
- `npm.cmd run build` passed (TypeScript and Vite production build)
- `npm.cmd run lint` passed (ESLint)
- `npm.cmd test` passed (17 tests covering HTTP 503 results, network/JSON failures, timeouts, cancellation, and recovery)
- Live `/api/health` and `/api/ready` requests through Vite returned HTTP 200 with healthy FastAPI results
- Vite served the requested browser title and refused a second server on occupied port 5173
- `git diff --check` passed; starter logos are absent, and `node_modules`/`dist` remain ignored
- Local Git status reviewed; the pre-existing untracked `Microsoft/` path remains untouched
- `frontend/package-lock.json` was staged and tracked during Step 2B (both lockfiles are now committed)

Step 2B decisions:
- Retained the existing React/TypeScript setup and matching Vite host, port, proxy, and browser title
- Use a five-second timeout covering response headers and the JSON body; disable refresh while requests run
- Read dependency results from HTTP 503 JSON, and allow a later refresh to recover after failures
- Added request tests with Node.js 24's built-in runner; no additional libraries
- Kept the frontend lockfile and documented `npm.cmd ci` for repeatable installation

Step 2B validation limits:
- Browser rendering, keyboard interaction, and rapid-click behavior were not exercised in a browser
- Failure/recovery scenarios use simulated responses; the running backend services were not stopped
- Vite's `/api` proxy applies only to development; production API routing is outside Step 2B
- No commits, pushes, or GitHub Actions were added

Step 2C local checks (2026-10-07; Windows host PowerShell and Linux Docker containers):
- `npm.cmd ci --no-audit --no-fund` passed in an isolated temporary frontend copy using the committed lockfile
- `npm.cmd run build` passed from the project frontend after restoring its dependencies
- `npm.cmd run lint` passed from the project frontend (ESLint)
- `npm.cmd test` passed from the project frontend (17 tests)
- `.\scripts\check-backend.ps1` passed: Compose validation, locked image build, startup, and 9 backend tests
- Real HTTP checks passed with `/health` HTTP 200 and `/ready` HTTP 200, then `/ready` HTTP 503 with both dependencies stopped while health remained HTTP 200, then ready HTTP 200 after restart
- Disposable containers, network, volume, and database settings were removed after the backend check
- `actionlint` 1.7.12 passed for `.github/workflows/ci.yml` in a temporary Linux container
- Workflow trigger, Ubuntu runner, and read-only permission assertions passed; PowerShell script syntax passed
- `git diff --check` passed; SHA-256 comparisons confirmed both committed lockfiles are unchanged
- Verified both disposable Compose projects were removed and the original development stack remains healthy

Step 2C decisions:
- Pull requests target `main`; pushes target `main` and `feat/local-foundation`; no deployment jobs or write permissions
- Use official checkout v7.0.1 and setup-node v7.0.0, verified from their release pages and pinned by full commit SHA
- Use Ubuntu 24.04 and Node.js 24; preserve `frontend/package-lock.json` and `backend/uv.lock`
- Generate local-only database settings per run; use project names containing the run ID and attempt to isolate containers and volumes
- Remove API host ports and source mounts only in the CI override; check the image's real running HTTP server
- Use bounded startup/HTTP checks, print service logs on failure, and always attempt disposable cleanup
- Preserve the existing unit test proving health never contacts either dependency; add HTTP checker failure tests

Step 2C limitations and corrections:
- GitHub CI verified on 2026-10-07: pull-request run #4 passed both Backend checks and Frontend checks.
- Initial CI runs failed because required CI files were not committed. Committing the Compose override, endpoint checker, Dockerfile change, and local verification script resolved the failure.
- No deployment or Step 3 implementation has been performed.
- Direct frontend `npm ci` initially failed because Windows locked a native Vite module; a clean temporary install succeeded, and missing local dependencies were restored with matching native binaries
- The first real outage check timed out with a three-second per-request cap; allowing each HTTP request its remaining 60-second overall budget fixed the check, and the full backend rerun passed
- Pytest passed with one Starlette TestClient/httpx deprecation warning from the committed dependencies; lockfiles were not changed

Step 2 manual verification (user confirmed):
- Browser displayed Supplier-Invoice-Verification and the API, PostgreSQL, and Redis status.
- Stopping PostgreSQL made readiness fail; restarting it restored readiness.
- Backend tests, frontend lint, and frontend production build passed.

Step 3.1 documentation work (2026-10-13; Windows host PowerShell):
- Read `AGENTS.md`, `docs/scope.md`, this progress record, and `README.md` before changes.
- Inspected all files under `backend/app`, `backend/tests`, and `frontend/src`, plus `backend/pyproject.toml`, `backend/Dockerfile`, both Compose files, `.github/workflows/ci.yml`, and `frontend/package.json`.
- Also inspected the Vite proxy, the disposable backend checker, and its HTTP endpoint-checking script to adapt the proposed layout and verification plan.
- Added `docs/manual-workflow.md` with the synthetic keyboard workflow, field-level schema and ownership constraints, decimal/date rules, API examples, frontend pages, proposed files, future checks, and scope comparison.
- Marked Milestone 2 completed and Step 3.1 in progress as requested; the blueprint is available for review and no Step 3 application implementation has begun.

Step 3.1 decisions proposed for review:
- Reuse FastAPI, synchronous SQLAlchemy/psycopg, PostgreSQL, React/TypeScript, Vite, and the existing status page and checks.
- Use a seeded local demo workspace, scoped API lookups, and composite database foreign keys; this is not authentication or a company security boundary.
- Use decimal strings for all quantities and money, backend decimal calculations, explicit per-line half-up rounding, and one manually entered invoice tax amount.
- Keep invoices in draft and expose only create/list/retrieve business endpoints with atomic document saves and bounded pagination.
- Propose Alembic for future migrations and no additional frontend dependency; identifier rules, numeric bounds, optional manual line mappings, and API contracts remain reviewable choices.
- No material conflict with `docs/scope.md` was found; the scope's discrepancy acceptance example and all later features remain deferred.

Step 3.1 checks actually performed:
- Initial `git status --short --untracked-files=normal` showed only the pre-existing untracked `Microsoft/`; post-edit status showed that path and the two intended documentation changes.
- Parsed all 12 synthetic JSON examples with PowerShell `ConvertFrom-Json`; verified 20 decimal fields use strings with the documented scales, pagination total is an integer, linked IDs agree, quantities are 10/8/10, invoice status/currency are draft/EUR, and example totals agree using decimal arithmetic.
- The first example checker incorrectly treated pagination `total` as a monetary field and failed. Corrected that checker to distinguish the integer count, then reran successfully; the examples did not require a change for that failure.
- A documentation structure check passed: eight numbered sections, all eight proposed tables, all four create/list/retrieve resource contracts, and the retained scope acceptance example.
- Reviewed the blueprint against `docs/scope.md` and the inspected implementation/configuration; no material scope conflict was found.
- `git diff --check` passed for tracked changes; the new blueprint's explicit trailing-whitespace check passed. Supplemental no-index comparisons against `NUL` returned exit 1 for new-file differences with no whitespace-error diagnostics; the first comparison also reported Git's LF-to-CRLF normalization warning.

Step 3.1 validation limits:
- No application tests, lint/build, Docker/Compose commands, migrations, seed commands, database operations, browser workflow, or GitHub CI were run in this documentation checkpoint.
- The actual `.env` file was not read, printed, modified, or created; pre-existing `Microsoft/` remains untouched.
- No application code, dependencies, lockfiles, Docker/Compose files, CI, or project scope was changed. No commit or push was performed.

Step 3.2 work (2026-10-13; Windows host PowerShell and Linux Docker containers):
- Read the project instructions, scope, progress, and reviewed blueprint before editing; inspected the application, tests, Docker/Compose configuration, CI, and PowerShell checker.
- Added shared safe database configuration, a bounded synchronous engine/session factory, and a request-scoped dependency with rollback/close and explicit caller commits. Reused the engine in `main.py`; health/readiness and lifespan shutdown behavior remain intact.
- Implemented all eight blueprint tables with shared SQLAlchemy metadata, PostgreSQL UUID/timestamp defaults, exact NUMERIC types, named checks/unique keys, indexes, and scoped composite foreign keys.
- Enforced optional invoice mapping pairs, invoice/order supplier consistency, and delivery/invoice line ownership. Explicit relationship joins designate which IDs may be written; order-line lookup relations and workspace collections are read-only. SQLAlchemy warnings fail tests rather than being suppressed.
- Added Alembic configuration and initial revision `0001_manual_records`, with explicit create/drop operations and no credentials or seed rows. Packaged migrations in the API image; application startup performs no schema or seed writes.
- Added disposable-target preparation/revision checks, opt-in PostgreSQL fixtures, session/guard tests, and real schema/ORM/rollback/migration tests.
- Extended the local checker and CI to prepare their guarded disposable database, apply migrations, inspect/verify the revision, and opt in to schema tests before the retained outage/recovery checks.
- Updated README with PowerShell build/migration/revision/test commands, isolation rules, and expected empty workspace tables. No business APIs, Pydantic business schemas, calculation services, demo seed command, or frontend features were added.

Step 3.2 dependency changes:
- Added direct `alembic>=1.16,<2.0`, locked to Alembic 1.20.0.
- The resolver added Mako 1.4.3 and MarkupSafe 3.0.4 as supporting dependencies.
- Regenerated `backend/uv.lock` using uv 0.8.22 and Python 3.12 inside a temporary Linux container. A version comparison against HEAD confirmed all 35 existing locked package versions were preserved.
- No host Python/uv installation or frontend dependency change was needed.

Step 3.2 isolation decisions:
- Disposable database/user are both `supplier_invoice_verification_test`; tests require explicit settings, host `db`, port `5432`, `RUN_POSTGRES_TESTS=1`, and an approved unique check/CI project name.
- Before migrations/tests, verify PostgreSQL's actual database/user/version and a database-comment marker matching that project. Preparation refuses nonempty unmarked databases and another project's marker. The destructive downgrade test repeats the connected marker guard.
- Per-test outer transactions and savepoints remove synthetic rows even when a test explicitly commits or recovers from an integrity failure. No SQLite persistence substitute or development-database fallback is used.
- Each checker/CI run has its own project/network/volume and generated temporary settings file. Only disposable resources are removed. Both Compose files, the development source mount, and frontend checks remain unchanged.

Step 3.2 checks actually performed:
- Migration generation configured all ORM mappers with SQLAlchemy warnings treated as errors; succeeded with no mapper warnings. Reviewed the generated initial migration, including dependency-safe downgrade order.
- Initial generator invocation failed because uv 0.8.22 `run` does not accept `--no-install-project`; removed that unsupported flag and reran successfully. No PostgreSQL schema check failed.
- PowerShell checker syntax passed; `git diff --check` passed.
- `.\scripts\check-backend.ps1` passed end to end: Compose configuration, locked image build, bounded startup, actual HTTP health/readiness, guarded database preparation, migration upgrade, `alembic current`, and verified head revision.
- Opted-in `pytest -q` inside the Linux API container passed: 115 tests, including 77 PostgreSQL integration cases, with no skips. Model/migration agreement, types/defaults/named constraints, valid and rejected links/values, relationship reads/writes, usable rollback, explicit session commits, repeated upgrade, and disposable downgrade/upgrade round trip passed.
- Actual HTTP checks passed: health/readiness HTTP 200 before migrations on an empty database; health HTTP 200 and readiness HTTP 503 while PostgreSQL and Redis were stopped; readiness HTTP 200 after restart.
- Ordinary `pytest -q -rs` in the built API image with Docker networking disabled passed: 38 tests and 77 integration skips with the explicit opt-in reason. No database connection was needed for this run.
- Cached actionlint container passed for `.github/workflows/ci.yml` without network access. Text comparison confirmed workflow triggers, read-only permissions, and the full frontend job are unchanged.
- Verified the disposable project's containers, network, volume, and temporary settings file were removed. Before/after Docker status showed the original development containers still running and PostgreSQL/Redis healthy.
- Git comparison confirmed `AGENTS.md`, `docs/scope.md`, `docs/manual-workflow.md`, both Compose files, and the entire frontend are unchanged. Pre-existing `Microsoft/` remains untouched.

Step 3.2 user verification:
- Disposable backend checker passed: 115 tests, exit code 0.
- Real HTTP health, dependency outage, and recovery checks passed.
- Development database migration applied successfully.
- alembic current reports 0001_manual_records (head).
- PostgreSQL table inspection confirmed eight application tables and alembic_version.
- Development /health and /ready returned healthy results.
- Online GitHub CI verification remains pending for Milestone 3.

Step 3.2 remaining checks and limits:
- Development migration and table inspection were subsequently completed by the user, as recorded above. Workspace initialization remains deferred to Step 3.3.
- GitHub Actions has not run on these uncommitted changes. Online CI remains pending until a separately authorized submitted revision is checked. Frontend tests/lint/build were not rerun because frontend files and that CI job are unchanged.
- Both pytest runs reported the existing Starlette TestClient/httpx deprecation warning. It did not fail tests; existing dependencies were preserved and no warning was suppressed.
- During Codex implementation, the actual .env was not read, printed, created, or modified, and the development database was untouched. The user subsequently applied the development migration. No database reset or deletion was performed.
- Local checks completed Step 3.2 only. Browser business workflows, seeding, business APIs/schemas/calculations, and all later milestone features remain unimplemented.

Step 3.3 work (2026-10-13; Windows host PowerShell and Linux Docker containers):
- Read the instructions, scope, blueprint, and progress before editing; inspected Step 3.2 models/sessions, migration, PostgreSQL fixtures, CI, and the disposable checker.
- Added shared fixed-workspace identity and `python -m app.seed_workspace`. Initialization creates only the expected local-demo workspace, is harmless to repeat, and rejects ID/slug/name conflicts without overwriting data. A reusable noncommitting helper supports the later full demo seeder.
- Added a demo-workspace request dependency, with generic HTTP 503 for a missing/conflicting workspace. All supplier/order reads, counts, filters, reference checks, and writes use this fixed workspace; clients cannot provide a workspace selector. This remains local demo context, not authentication.
- Added strict Pydantic supplier/order create/read/list contracts, nested order lines, trimmed text, nullable notes, bounded pagination, exact calendar dates, and forbidden extra/server-owned fields.
- Decimal requests require plain strings with the blueprint's length/scale/range limits; response quantities/prices/money use fixed 3/4/2 fractional digits. Added reusable Decimal helpers with precision 38, per-line ROUND_HALF_UP, sum of rounded cents, and calculated-overflow rejection before insertion.
- Added POST/list/retrieve routes for `/suppliers` and `/purchase-orders`, HTTP 201/200 and Location headers, supplier ownership checks, stable list ordering/filtering, and order details with ordered lines. Whole documents commit once and return success only afterward.
- Added business-only sanitized 422/404/409/503/500 envelopes. Database uniqueness constraints handle conflicting creates with rollback; errors do not echo submitted values, unknown keys, SQL, connection strings, or raw exception messages. Health/readiness handlers are unchanged.
- Extended guarded PostgreSQL fixtures so each API request uses a fresh session and commits a savepoint inside the test's outer transaction. Added actual API persistence, decimal, isolation, seed-conflict, rollback, commit-failure, error-redaction, and recovery tests; retained all foundation/schema tests.
- The local checker and CI now execute workspace initialization twice after pytest, before existing outage/recovery checks. CI adds `feat/manual-invoice-workflow` to push branches and preserves the previous branches, pull-request trigger, frontend job, and read-only permissions.
- Updated README with initialization, synthetic API verification, pagination/decimal/error rules, and disposable-test commands. No genuine schema issue was found; the applied initial migration and all models were preserved.

Step 3.3 dependency changes:
- Declared direct `pydantic>=2.0,<3.0`, retaining locked Pydantic 2.13.5.
- Regenerated `backend/uv.lock` with uv 0.8.22/Python 3.12 inside a temporary Linux container. All 38 existing locked package versions were preserved and no package was added.
- No host Python/uv installation, frontend dependency change, cloud resource, or paid service was used.

Step 3.3 checks actually performed:
- The first disposable run built/applied migrations and ran 258 tests: 256 passed and two failed. One test helper supplied `supplier_id` twice; the error sanitizer also omitted the known `description` field label. Corrected both findings and reran the full checker. Its failed run still removed its disposable resources.
- Final `.\scripts\check-backend.ps1` passed end to end: Compose validation, locked image build, bounded startup, unchanged real health/readiness, disposable database guard, migration upgrade, and head revision `0001_manual_records`.
- Final opted-in pytest passed: 258 tests, no skips, including 172 PostgreSQL/API/workspace cases and 86 other checks. Create/list/retrieve persistence, trimming/optional values, strict decimals, rounding/bounds/overflow, pagination/filtering, UUID/record/reference failures, cross-workspace exclusion, duplicate-key rollback, and later valid requests passed.
- Real PostgreSQL line-trigger failure left no partial order/lines and returned sanitized HTTP 500. An injected failure after flushed rows but before commit returned sanitized HTTP 503, rolled back the whole document, and permitted a later valid request. API commits did not leak rows into subsequent tests.
- Workspace initialization twice, all conflicting ID/slug/name arrangements, noncommitting helper reuse, missing-workspace HTTP 503, and no implicit request seeding passed. The checker executed the actual module command twice successfully after pytest; no business records were seeded by the command.
- Retained real HTTP outage/recovery checks passed: health/readiness HTTP 200 before migrations/initialization, health HTTP 200 with readiness HTTP 503 while PostgreSQL/Redis stopped, then readiness HTTP 200 after restart.
- Ordinary pytest in the final API image with Docker networking disabled passed: 86 tests and 172 explicit integration skips; no database connection was needed.
- Cached actionlint container passed without network access; PowerShell checker syntax passed. All ten README PowerShell blocks parsed after correcting the documentation checker to recognize Windows CRLF closing fences and require blocks to be found.
- Lockfile package-version comparison passed. Git comparison confirmed the project instructions/scope/blueprint, database session module, models, Alembic configuration/migrations, Dockerfile, both Compose files, and complete frontend are unchanged.
- Verified cleanup of both disposable projects' containers/networks/volumes/settings files. Before/after Docker status showed the development API still running and its PostgreSQL/Redis healthy. No development database operations were performed by Codex.
- `git diff --check` passed; final change scope and new-file whitespace were reviewed.

Step 3.3 remaining checks and limits:
- The user still needs to rebuild the development API and run explicit workspace initialization, then verify the README's synthetic supplier/order requests if desired. These development writes were not performed by Codex.
- Online GitHub CI remains pending on a separately authorized submitted revision; actionlint/local checks do not establish an online CI pass. No commit or push was performed.
- The existing Starlette TestClient/httpx deprecation warning remains in both pytest runs; it did not fail tests and was not suppressed. Compatible dependency versions were preserved.
- Frontend tests/lint/build and a business browser workflow were not run; frontend files are unchanged and no business pages were implemented.
- The actual `.env` was not read, printed, created, or modified; `Microsoft/` remains untouched. No development reset/deletion, applied migration rewrite, or other milestone implementation occurred.

Step 3.3 user verification:
- Disposable backend checker passed: 258 tests, exit code 0.
- Dependency outage and recovery checks passed.
- Development database remains migrated to the current head.
- Demo workspace initialization succeeded twice.
- Supplier creation returned HTTP 201.
- Purchase-order creation returned HTTP 201 with subtotal "250.00".
- Purchase-order retrieval succeeded through Swagger UI and PowerShell.
- A line-item ID initially returned 404 when used as an order ID; using the header ID resolved the request.
- Online GitHub CI verification remains pending.

Step 3.4 implementation and decisions:
- Added create/list/retrieve delivery-receipt and draft-invoice schemas and six endpoints using the existing fixed-workspace/session dependencies. Clients cannot select a workspace or supply server-owned fields, status, totals, or internal line order IDs.
- Receipts require an existing scoped purchase order and its lines, reject duplicate order-line entries within one receipt, assign ordered line numbers, and copy the internal order ID on the server. Multiple receipts and positive overdelivery are accepted; cumulative quantity comparisons remain deferred.
- Invoices require a scoped supplier and optionally one order from that supplier. Optional manual mappings must refer to the selected order; no order means no mapped lines. Unmapped lines and repeated invoice mappings are allowed. Every invoice receives server-assigned draft status.
- Reused strict decimal-string validation and per-line HALF_UP rounding. Factored the existing purchase-order line calculation into a shared helper without changing its behavior; added explicit cent-scale tax validation and invoice subtotal-plus-tax addition using local Decimal precision 38. Line, subtotal, and final total overflow are rejected before insertion.
- Extended the existing atomic save/error handling for scoped delivery/invoice uniqueness constraints. Each document commits once before success; failures roll back all rows. Scoped missing references are 404; incompatible in-workspace relationships and invalid input are 422; errors remain sanitized.
- Added a common documented business error model to BusinessRoute, so all 12 business operations advertise error.code/error.message/error.details for 422/404/409/503/500. This corrects the Swagger documentation mismatch; the existing runtime validation was already using that envelope. Health/readiness handlers and documentation contracts are preserved.
- Added guarded PostgreSQL workflow, persistence, relationship, filtering, validation, tax, overflow, rollback/recovery, and commit-isolation tests. Added OpenAPI contract tests and invoice calculation unit tests. Updated the old deferred-route assertion to cover approval/export endpoints, since delivery/invoice routes are now implemented.
- Updated README with synthetic delivery/invoice PowerShell examples, retrieval of the previously created supplier/order, optional mapping rules, invoice totals, and Swagger verification.
- No schema issue was found. Models, the applied initial migration, Alembic configuration, database sessions, dependencies/lockfiles, Docker/Compose files, workspace initialization, and frontend are unchanged. The existing checker and CI already collect all new tests with PostgreSQL opt-in; their guards, outage/recovery checks, frontend job, triggers, permissions, and cleanup needed no changes.

Step 3.4 checks actually performed:
- First disposable checker run applied migrations and ran 466 tests: 465 passed and one new test failed because its helper supplied supplier_id twice. Corrected that helper; no runtime/API defect was identified by the failure. Its disposable resources were cleaned up.
- Final `.\scripts\check-backend.ps1` passed end to end with exit code 0: Compose validation, locked image build using Python 3.12 inside Docker, bounded startup, actual HTTP health/readiness, disposable database guard, migration upgrade, and revision `0001_manual_records (head)`.
- Final opted-in pytest passed: 466 tests, no skips (351 PostgreSQL/API/workspace cases and 115 other checks). All retained foundation, schema, supplier/order, and workspace tests passed alongside the new delivery/invoice and OpenAPI cases.
- The stored 10 ordered / 8 delivered / 10 invoiced workflow passed, including real nested-row persistence, linked record retrieval, server-generated IDs/timestamps, fixed decimal scales, ordered lines, and header-only lists.
- Missing/cross-workspace references, wrong suppliers/orders/lines, duplicate receipt entries, optional order/mapping combinations, duplicate scoped identifiers, pagination/filtering, malformed UUIDs/JSON, decimal strings/bounds, dates/currency, client-supplied status/totals/internal fields, HALF_UP rounding, tax addition, and all three invoice overflow levels passed.
- For each new document type, an actual PostgreSQL trigger failure on the second line returned sanitized 500 and left no header or lines. Injected failure after flushed rows but before commit returned sanitized 503 without Location/success and left no partial document. A subsequent valid create succeeded using the same document identifier. Per-test rollback removed committed rows and trigger DDL.
- The checker executed explicit workspace initialization twice successfully after pytest, then retained actual HTTP outage/recovery checks passed: health 200/readiness 200 initially; health 200/readiness 503 while PostgreSQL/Redis stopped; readiness 200 after restart.
- Ordinary pytest in the final Linux API image with Docker networking disabled passed: 115 tests and 351 PostgreSQL skips, each with the explicit opt-in reason. It required no database connection or host Python installation.
- All 14 README PowerShell blocks parsed successfully; PowerShell checker syntax passed. These documentation examples were syntax-checked, not executed against the development API.
- Git comparison confirmed the instructions/scope/blueprint, database/session/model/migration files, dependencies/lockfile, workspace initialization/dependency, PostgreSQL fixtures, Docker/Compose files, checker/CI, and complete frontend are unchanged. `git diff --check` and explicit new-file whitespace checks passed.
- Verified both disposable projects removed their containers, networks, volumes, and generated temporary settings files. Before/after Docker status showed the development API still running and its PostgreSQL/Redis healthy. No development database operations were performed.

Step 3.4 remaining verification and limits:
- From Windows PowerShell, the user can repeat isolated checks with `.\scripts\check-backend.ps1`, then rebuild the development API with `docker compose up --build -d api` and inspect `http://127.0.0.1:8000/docs`. The README has exact synthetic delivery/invoice commands. Development migration/workspace initialization was already reported complete in the Step 3.3 user verification; Step 3.4 requires no new migration or seed command.
- Manual development requests and browser/Swagger inspection were not performed by Codex, to preserve development database contents. Automated TestClient requests used only the approved disposable PostgreSQL database.
- Online GitHub CI remains pending on a separately authorized submitted revision. No commit or push was performed. Frontend lint/tests/build were not rerun because frontend files are unchanged; CI retains those checks.
- The existing Starlette TestClient/httpx deprecation warning remains, unsuppressed; it did not fail either final test run. No new dependency was necessary.
- The actual `.env` was not read, printed, created, or modified; `Microsoft/` remains untouched. No development data changes, migration rewrite, frontend work, or later milestone implementation occurred.

Step 3.4 user verification:
- Disposable backend checker passed: 466 tests, exit code 0.
- Dependency outage, recovery, and disposable cleanup passed.
- Delivery creation returned HTTP 201.
- Delivery retrieval returned HTTP 200 with quantity_received "8.000".
- Invoice creation returned HTTP 201.
- Invoice retrieval returned HTTP 200 with draft status and total "250.00".
- Delivery and invoice records reference the intended purchase order and line.
- Online GitHub CI verification remains pending.

Step 3.5A implementation and file purposes:
- Updated `frontend/src/App.tsx` to show the exact Supplier-Invoice-Verification name, Status/Suppliers/Purchase orders navigation, hash routes, a useful unknown-page state, page focus, and per-form drafts/feedback that stay in memory across navigation. Updated `App.css` for labeled forms, feedback, visible focus, paginated lists, tables, and narrow-screen layouts.
- Extracted `frontend/src/pages/StatusPage.tsx` from the existing App. Preserved the status card/check/refresh logic, five-second status requests, cancellation, independent updates, recovery messages, and immediate repeat-click guard. The status request module and original 17 tests are unchanged.
- Added `types.ts` for actual supplier/order create/read/list contracts and string decimals; `validation.ts` for text/date/decimal/line limits, accepted-field payloads, stable unsaved line keys, indexed messages, and first-error focus; `api.ts` for native proxy requests, five-second full-body bounds, response-format checks, business error mapping, and uncertain dispatched writes.
- Added `navigation.ts` for implemented hash routes, pagination/filter serialization and bounds, and hash-change subscriptions. Added `requestScope.ts` completion/cancellation guards and `hooks/useBusiness.ts` for read retries, obsolete-read cancellation, guarded saves, and protection against late responses redirecting a different page.
- Added `components/Navigation.tsx`, `Pagination.tsx`, and `RequestState.tsx` for active navigation, bounded page controls/counts, and loading/retry/error states. Added `FormFeedback.tsx` for labels, hints, inline errors, an error summary, and uncertain/conflicting save list checks.
- Added `components/SupplierPicker.tsx` to fetch suppliers in pages of 20, retain a selected code/name across pages, and explain/link creation when none exist. Added `LineItemsForm.tsx` for unsaved description/quantity/price rows with stable keys and 1-100 add/remove limits. Added `PurchaseOrderList.tsx` for reusable scoped/filterable order summaries and pagination.
- Added `pages/suppliers/SupplierListPage.tsx`, `SupplierNewPage.tsx`, and `SupplierDetailPage.tsx` for paginated code/name browsing, supplier creation, saved fields, and paginated linked orders. Added `pages/purchase-orders/PurchaseOrderListPage.tsx`, `PurchaseOrderNewPage.tsx`, and `PurchaseOrderDetailPage.tsx` for number/date/EUR-subtotal browsing, nested creation, and saved supplier/header/line/subtotal views.
- Added `frontend/tests/api.test.mjs`, `navigation.test.mjs`, and `validation.test.mjs` using the existing Node runner. Updated README with routes, behavior, Windows PowerShell commands, and remaining manual browser checks.

Step 3.5A decisions and limits:
- Reused React, TypeScript, Vite, CSS, native fetch, and simple hash navigation. Empty hash opens Status; canonical detail IDs and bounded page parameters support deep links/history. Delivery/invoice routes remain absent from functional website navigation until Step 3.5B.
- Prices, quantities, line totals, and subtotals remain strings. Decimal bounds are checked by digit comparison, without binary floating-point conversion. The website does not calculate financial products, rounding, or totals; saved totals come from the backend. Integer conversion is limited to calendar dates and pagination/count handling.
- Form payloads contain only accepted fields; local keys, IDs/workspace/timestamps, line numbers, and totals are omitted. EUR is fixed. Text is trimmed for submission, blank notes become null, dates stay calendar strings, and invalid decimal notation/scale/ranges are rejected locally while server validation remains authoritative.
- Each read has cancellation and completion guards. Writes have an immediate controller guard plus disabled controls during saving. No POST is automatically retried. Dispatched network/timeout/cancelled/invalid-success responses may have saved the record; inputs and warning remain, with a list check opening a new tab before a manual retry.
- Supplier/order drafts and error feedback are held only in React memory. Navigation/Cancel retains them within the tab; success clears the corresponding draft and navigates using the saved header ID. Full reload clears unsaved input; saved-record detail/list routes reload from the API. No browser storage or hardcoded local record IDs were added.
- No dependency, lockfile, Vite proxy, backend, Docker/Compose, checker, or CI change was needed. Existing CI's frontend job discovers the new test files via `npm test`, then retains lint/build. No applied migration, demo seed, editing/deletion of saved records, or later milestone feature was implemented.

Step 3.5A checks actually performed (Windows host PowerShell):
- Read the instructions, scope, blueprint, and progress before editing; inspected frontend source/tests/scripts/configuration and backend supplier/order schemas, endpoints, and error contracts. Initial Git status showed only pre-existing untracked `Microsoft/`.
- Confirmed Node.js v24.21.0 and npm 11.19.0 with the existing installed dependencies; no install or dependency resolution was required.
- Initial production build failed on TypeScript narrowing of an order response's nested lines after checking the summary type. Captured/validated the lines array before the summary guard and corrected the build. No frontend helper test failed.
- Final `npm.cmd test` passed: 99 tests, no failures or skips, including all 17 original status tests and 82 new cases. New checks cover nested accepted payloads, exact decimal strings/output scales, pagination/filter queries, HTTP error envelopes, sanitized unknown failures, input bounds, calendar dates, stable keys, field-focus helper behavior, simulated hash/history events, obsolete completion guards, full-body timeouts, cancellation, uncertain writes, no automatic POST retries, and later explicit read recovery.
- Final `npm.cmd run lint` passed; final `npm.cmd run build` passed TypeScript and Vite production compilation (37 modules). Build artifacts remain ignored.
- Compared the extracted status logic against the original App from Git: labels, cards, state, refresh implementation, cleanup, and recovery-note logic match. Existing `status.ts` and `tests/status.test.mjs` are unchanged.
- All 15 README PowerShell blocks parsed successfully. `git diff --check` passed; explicit whitespace/final-newline checks passed for all 23 new frontend/test files.
- Git comparison confirmed instructions/scope/blueprint, the complete backend, both dependency manifests/lockfiles, proxy configuration, frontend entry/browser title/base CSS/status requests/tests, Docker/Compose files, scripts, and CI are unchanged.

Step 3.5A remaining checks:
- No browser was exercised. Rendering, actual Back/Forward/refresh/deep-link behavior, keyboard/radio controls, focus, narrow-screen table scrolling/layout, double-click Save handling, real creates, and lost/delayed-response navigation remain unverified in a browser. The mocked/helper tests do not prove the real browser workflow or PostgreSQL persistence through these pages.
- README lists the manual synthetic-browser checks and exact frontend commands. Existing fictional records can be used for read-only browsing; creation checks should use the chosen synthetic verification stack.
- Backend tests/disposable checker were not rerun in this frontend-only checkpoint. No development database contents were read or modified through API/SQL calls; frontend tests used only simulated fetch responses. The actual `.env` was not read, printed, created, or modified, and `Microsoft/` remains untouched.
- Online GitHub CI remains pending on a separately authorized submitted revision. No commit, push, cloud resource, or deployment was performed.

Step 3.5A user verification:
- Frontend tests passed: 99 tests.
- Frontend lint and production build passed.
- Supplier and purchase-order website creation worked.
- Saved order details showed the correct supplier, quantities, prices, and EUR totals.
- Refresh, supplier links, browser Back/Forward, and keyboard navigation worked.
- Status page continued to show healthy services.
- Remaining browser scenarios, including interrupted writes and narrow layouts, require later verification.

Step 3.5B implementation and file purposes:
- Updated `frontend/src/App.tsx`, `navigation.ts`, and `components/Navigation.tsx` to register delivery/invoice list/new/detail pages and the Delivery records/Invoices links while retaining the exact Supplier-Invoice-Verification name and existing routes. Hash lists preserve bounded pagination and supported filters; the website delivery path maps to backend `/delivery-receipts`.
- Extended `types.ts`, `validation.ts`, and `api.ts` with actual delivery/invoice request, saved-record, list, draft, and filter contracts; accepted-field payload projection; string quantities/prices/tax; required explicit tax; dates/due dates; line limits and membership; receipt duplicate checks; and canonical saved decimal/status formats. All calculations remain on the backend.
- Added `selections.ts` for synchronous dependency clearing and selected-order identity checks; added `hooks/useSelectedOrder.ts` for keyed, cancelled, guarded detail reads. Switching delivery order clears its lines; switching invoice supplier clears its order/mappings; switching invoice order clears mappings. Other fields and invoice line keys are preserved, and old fulfilled requests never repopulate drafts.
- Added `components/OrderPicker.tsx` for readable paginated order choice, optional no-order selection, and supplier-filtered invoice orders. Invoice order pickers are keyed by supplier ID so paging resets with a changed supplier. Extended `SupplierPicker.tsx` with a contextual empty hint while preserving its order-form default.
- Extended `components/FormFeedback.tsx` with labeled/selectable inline-error fields and `LineItemsForm.tsx` with optional descriptive manual invoice mappings. Added select/checkbox focus and responsive styling in `App.css`; retained existing save guards, request scopes, error envelopes, uncertain-write list checks, and in-memory draft behavior.
- Added `components/DeliveryList.tsx`, `InvoiceList.tsx`, and `SupplierLink.tsx` for shared independently loaded/paginated summaries and readable supplier navigation.
- Added `pages/deliveries/DeliveryListPage.tsx`, `DeliveryNewPage.tsx`, `DeliveryLinesForm.tsx`, and `DeliveryDetailPage.tsx`. Creation chooses current order lines by description/checkbox, enters positive string quantities, rejects duplicates, waits for the current order detail, and navigates using the saved receipt header ID. Saved receipt quantities remain visible if its separate order-description/supplier lookup fails.
- Added `pages/invoices/InvoiceListPage.tsx`, `InvoiceNewPage.tsx`, and `InvoiceDetailPage.tsx`. Creation supports supplier, optional filtered order, required tax initially blank, optional due date, priced lines, optional/null manual mappings, and saved header-ID navigation. Details show draft status, saved lines/links, and authoritative subtotal/tax/total strings.
- Extended `pages/purchase-orders/PurchaseOrderDetailPage.tsx` with separate delivery/invoice sections using existing order/supplier filters; extended `pages/suppliers/SupplierDetailPage.tsx` with filtered invoices. New related lists own their paging, read, retry, loading, and error state; one failed lookup does not hide the saved header or other sections.
- Added `frontend/tests/delivery-invoice.test.mjs` and updated `tests/navigation.test.mjs` to recognize the now-implemented routes and test their filter/pagination rules. Updated README with routes, selection behavior, request/uncertainty rules, and the synthetic 10/8/10 manual browser checklist.

Step 3.5B decisions:
- No new dependency or architectural replacement was required. Reused React/TypeScript, CSS, native fetch, the Vite proxy, hash navigation, five-second full-body requests, pagination, completion scopes, error handling, and guarded saving.
- Delivery/invoice requests contain only backend-accepted fields. Server-owned IDs/workspaces/timestamps/status/totals/internal line order IDs and local line keys are omitted. Decimal input is not coerced, financial values remain strings, and no financial calculation, automatic mapping, cumulative-quantity comparison, or discrepancy flag is performed by the website.
- Positive overdelivery/multiple receipts, no-order invoices, unmapped lines on selected orders, and repeated invoice mappings remain valid as specified by the backend. Tax must be entered explicitly, including `0.00`; the website does not infer tax or copy priced values when mapping.
- New drafts and save feedback remain only in React memory across same-tab navigation. Failure retains input; success clears the corresponding draft. Full reload clears unsaved values but saved list/detail routes read from the API. Interrupted writes may be saved and offer list inspection in a new tab before manual retry; POST requests are never automatically retried.
- No backend, migration, seed, dependency/lockfile, Docker/Compose, proxy, existing request-scope/save hook, status page/request/test, or CI change was necessary. The existing frontend CI wildcard discovers the new test file. No saved-record editing/deletion or later milestone feature was added.

Step 3.5B checks actually performed (Windows host PowerShell):
- Read the instructions, scope, blueprint, and progress before changes; inspected existing frontend architecture/requests/navigation/forms/selectors/tests and actual backend delivery/invoice schemas, routers, and validation. Initial Git status showed only pre-existing untracked `Microsoft/`.
- Confirmed existing Node.js v24.21.0 and npm 11.19.0; no install or dependency resolution was required.
- Focused new delivery/invoice test file passed: 34 mocked/helper tests, no failures or skips. An independent read-only contract/lifecycle review found no blocking issue; the reused supplier empty hint was made contextual for invoices.
- Final `npm.cmd test` passed: 140 tests, no failures or skips. All original status tests and supplier/order/API/validation/lifecycle checks passed; obsolete delivery/invoice absent-route assertions were replaced with implemented-route coverage. New checks cover accepted nested payloads, dependent-selection clearing/stable keys, obsolete response rejection, optional/manual/repeated mappings, decimals/tax/date/text/line bounds, overdelivery allowance, filters, saved response formats, business errors, cancellation/full-body timeouts, uncertain writes, no automatic retries, and explicit read recovery.
- Final `npm.cmd run lint` passed; final `npm.cmd run build` passed TypeScript and Vite production compilation (50 modules). Initial full build/lint also passed. No failing automated check required an implementation correction in this checkpoint.
- All 16 README PowerShell blocks parsed successfully. `git diff --check` passed; explicit trailing-whitespace/final-newline checks passed for all 14 new frontend/test files. Build output and node_modules remain ignored.
- Git comparison confirmed the complete backend, instructions/scope/blueprint, manifests/lockfiles, Docker/Compose files, scripts/CI, Vite proxy, frontend entry/browser title/base CSS, status page/module/tests, request scopes, existing read/save hooks, and previous API/validation tests are unchanged.

Step 3.5B remaining verification and limits:
- No browser was exercised. Real Back/Forward/refresh/deep-link behavior, radio/checkbox/select keyboard control, first-error focus, narrow layouts, full synthetic 10/8/10 saves/persistence, pagination beyond page one, independent related-list failures, repeat Save clicks, and delayed/interrupted navigation remain unverified in a browser. Mock/helper tests do not establish those real workflows.
- README lists exact frontend check/start commands and manual scenarios. Existing fictional records can support read-only checks; creation checks belong in the chosen synthetic verification stack. No real API/SQL/browser commands or development database writes were performed by Codex; frontend requests in tests were mocked.
- Backend tests/disposable checker were not rerun for this frontend-only checkpoint. Online GitHub CI remains pending on a separately authorized submitted revision. No commit or push was performed.
- The actual `.env` was not read, printed, created, or modified; `Microsoft/` remains untouched. No cloud resource, paid service, dependency addition, deployment, seeding, authentication, uploads, AI, approval, or export work occurred.

Step 3.5B user verification:
- Frontend tests passed: 140 tests, no failures or skips.
- Frontend lint and production build passed.
- User confirmed the delivery/invoice website workflow works.
- Detailed final browser verification remains part of Step 3.6.
- Online CI verification for the final Milestone 3 revision remains pending.

Next task:
- Stop after Step 3.5B and await the next requested checkpoint.
- Record user-run browser verification and future online CI results separately from the completed mock/helper checks.
- Keep full demo seeding, saved-record editing/deletion, authentication, uploads, AI, automatic matching, approval, notifications, exports, and cloud infrastructure deferred.

Blockers: None recorded.
