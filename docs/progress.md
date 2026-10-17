# Progress

Current milestone: 4 - Authentication and workspace authorization (implementation and validation complete)
Current task: Merge pull request #3 and synchronize local main

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
- Completed Step 3.6 repeatable fictional demo seeding and disposable API persistence verification
- Completed Step 4.1 repository inspection and authentication/workspace authorization design in `docs/auth-workspaces.md`
- Completed Step 4.3 additive identity/membership persistence, explicit operator bootstrap, and guarded PostgreSQL verification
- Completed Step 4.4 Cognito access-token verification, workspace permissions, identity/workspace/membership APIs, and authenticated disposable HTTP checks
- Completed Step 4.5 browser PKCE login, memory session lifecycle, workspace-aware requests, onboarding/administration UI, and synthetic frontend verification

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

Step 3.6 implementation and file purposes:
- Added `backend/app/seed_demo.py`: explicit `python -m app.seed_demo`, fixed blueprint workspace/header/line IDs, exact fictional 10 ordered / 8 received / 10 invoiced workflow, insert-or-verify behavior, safe conflict/failure exits, and one transaction for the whole fixture.
- Updated `backend/app/services/manual_records.py` minimally to expose noncommitting validated model builders shared by API creates and seeding. Existing APIs still use the same save helper, commit before success, and roll back/translate errors as before. Reused create schemas, scoped reference validation, money helpers, and the existing noncommitting workspace initializer.
- Added `backend/tests/test_seed_demo.py`: opted-in PostgreSQL proofs of exact records/links/totals/draft status, repeatability including timestamps, missing-record repair, global fixed-ID and scoped natural-key conflicts, mismatched fields/mappings/extra lines, preservation of MANUAL-/UI-/other-workspace data, late database/commit failure rollback, CLI exits, next-request recovery, and test isolation.
- Added `backend/scripts/check_demo.py`: guarded disposable-only invocation of the real seed command twice, live detail/list/filter reads, returned IDs/decimal values, status-specific OpenAPI example checks, retained full JSON snapshot, and comparison after actual API/PostgreSQL restart. Added `backend/tests/test_check_demo.py` for response/line/count/example checks, request deadlines, sanitized failures, opt-in refusal before connection/seeding/snapshot access, and capture/verify lifecycle.
- Updated `scripts/check-backend.ps1` and `.github/workflows/ci.yml` to use that shared demo checker before/after restarting API and PostgreSQL without deleting their volume. Preserved migrations/revision checks, unique projects, generated disposable settings, guards, read-only GitHub permissions, bounded waits, failure logs, outage/recovery checks, frontend CI, and disposable cleanup.
- Updated `backend/app/schemas/errors.py` and `backend/tests/test_openapi.py` so each documented business status illustrates its actual error code: 422 validation_error, 404 not_found, 409 conflict, 503 service_unavailable, 500 internal_error. The runtime envelope, handlers, routes, and health/readiness contracts remain unchanged.
- Updated README with current scope, fresh build/migrate/seed/frontend instructions, fixed IDs, repeatability/conflict behavior, and disposable persistence checks. Added `docs/demo.md` with the short read-only browser demonstration and remaining browser scenarios. Updated this progress record.

Step 3.6 decisions and limits:
- The fixture uses the blueprint dates, supplier notes, optional invoice due date 2026-11-14, and explicit manual invoice-line mapping. It retains EUR, tax 0.00, total 250.00, and draft status. The difference between ordered/invoiced 10 and received 8 is visible as manual records; no discrepancy detection is added.
- Existing fixed IDs and scoped keys must identify exactly the expected fixture, including its business fields and only its expected document line. Existing matching timestamps are preserved. Missing expected rows are inserted; existing rows are never adopted, updated, or renamed. Earlier API-created DEMO-* identifiers with generated IDs deliberately conflict even if visible values match.
- Both workspace and business records belong to a single seed transaction. A conflict, line insert failure, or commit failure rolls back all new rows; no workspace-only intermediate commit is introduced. No import or startup invokes seed writes. Unrelated records and identical identifiers in other allowed scopes are preserved.
- Tests retain the approved disposable PostgreSQL target and outer-transaction/savepoint fixtures, including when services or the seed commit. The shared live checker requires explicit integration opt-in, approved generated settings, the connected PostgreSQL 17 database/user and matching project marker, and migration head before invoking the seed. It has no development database fallback.
- No dependency, lockfile, model, applied migration, database session, workspace initializer, fixture, Docker/Compose, or frontend change was necessary. No cloud resource, infrastructure, saved-record editing/deletion, authentication, uploads, AI, automatic matching, approval, notification, or export feature was added.

Step 3.6 checks actually performed (2026-10-13; Windows host PowerShell, Python/checks inside Linux containers):
- Read AGENTS.md, scope, blueprint, and progress before editing; inspected models, schemas/services, workspace seeding, fixtures/tests, Docker/Compose, checker, CI, and README. Initial Git status showed only pre-existing untracked `Microsoft/`.
- `.\scripts\check-backend.ps1` passed, exit code 0, using project `supplier-invoice-verification-check-9918054979094a358f74631276b70576`. The Docker build retained locked dependencies. Guarded migrations applied and verified `0001_manual_records (head)`, and all 530 tests passed with PostgreSQL integration opt-in: no failures or skips. Existing foundation/schema/workspace/business API tests were retained.
- The same checker ran workspace initialization twice, then the actual `python -m app.seed_demo` command twice. Live HTTP detail/list/filter reads confirmed fixed header/line IDs, exact links, one fixture line per document, ordered 10.000, received 8.000, invoiced 10.000 at 25.0000, tax 0.00, total 250.00, and draft status. The two full snapshots, including timestamps and counts, matched.
- Restarted only that disposable project's API/PostgreSQL containers with the volume retained. Bounded recovery returned `/health` 200 and `/ready` 200; fresh live API reads matched the retained snapshot exactly. Live OpenAPI responses advertised the appropriate business error example for each status on all 12 business operations.
- Retained actual outage/recovery verification: stopping disposable PostgreSQL/Redis kept `/health` 200 and made `/ready` 503 with both unavailable; starting them restored `/ready` 200 with both healthy. The checker removed its containers, network, volume, and generated temporary settings file.
- Ran ordinary `pytest -q -rs` in the new API image with `docker run --rm --network none` and no opt-in/database: 142 tests passed, 388 PostgreSQL tests skipped with the explicit disposable-opt-in reason, exit code 0. No development database connection was possible.
- Validated the changed GitHub workflow with cached `rhysd/actionlint:1.7.12`, networking disabled: passed, exit code 0. Parsed the PowerShell checker successfully; all 21 README/demo PowerShell blocks parsed successfully. Final `git diff --check` and whitespace/final-newline checks on all 12 changed/new files passed.
- Final Docker metadata confirmed the disposable project's containers, network, volume, and generated temporary settings were absent. Before/after status showed the development API still running and its PostgreSQL/Redis healthy. Git comparison confirmed frontend, dependencies/lockfiles, models, sessions, workspace initializer, fixtures, migrations, Docker/Compose, instructions, scope, and blueprint unchanged.
- Both test runs reported the existing unsuppressed Starlette TestClient/httpx deprecation warning. It did not fail checks; no unrelated dependency change was made.

Step 3.6 remaining manual/online checks:
- Follow `docs/demo.md` after deliberately choosing and initializing a local fictional demo database. Codex did not run this seed against development, use its API/SQL records, or exercise a browser. Final rendering, links/history/deep links, keyboard/narrow layout, selector pagination, input/failure recovery, uncertain saves, and stale-response navigation still need actual browser observations. Existing Step 3.5A/3.5B user observations above remain separate evidence.
- Online GitHub CI for the final Milestone 3 revision remains pending; actionlint and the local disposable run do not establish an online pass. No commit or push was performed.
- Frontend checks were not repeated because frontend files are unchanged; the previous 140-test/lint/build results remain historical evidence, and the existing frontend CI job remains intact.
- The actual `.env` was not read, printed, created, or modified; `Microsoft/` remains untouched. No development database contents were changed. Use `.\scripts\check-backend.ps1` for repeatable isolated backend verification; README/demo guide provide exact opt-in local setup commands separately.

Step 3 final verification:
- Codex reported 530 backend tests passing in the disposable checker.
- Disposable verification confirmed repeated seeding and persistence after API/PostgreSQL restart.
- User-run frontend checks passed: 140 tests, lint, and production build.
- User confirmed the manual website workflow works.
- GitHub push and pull-request backend/frontend checks passed for commit 201d47b.
- Pull request #2 contains the completed Milestone 3 implementation.
- Authentication, AI extraction, automatic discrepancy detection, and approval remain later milestones.
- User verified repeated development seeding and the linked PO-DEMO-001, DR-DEMO-001, and INV-DEMO-001 browser demonstration.

Previous Milestone 3 handoff (historical; remote merge/local synchronization not verified in Step 4.1):
- Merge pull request #2 after the latest checks pass, then synchronize local main.
- Review Milestone 4 skills and scope before implementation.

Step 4.1 documentation work (2026-10-17; Windows host PowerShell):
- Read `AGENTS.md`, `docs/scope.md`, this progress record, and `docs/manual-workflow.md`; inspected backend sessions, models/migration, routers/errors/services, the fixed-workspace dependency, both seed commands, frontend navigation/request lifecycle, test fixtures, disposable schema/HTTP checkers, Docker/Compose configuration, CI, and dependency manifests.
- Added `docs/auth-workspaces.md` as the later implementation contract: Cognito public client, code flow with PKCE using oidc-client-ts, PyJWT/cryptography verification, exact verified issuer/subject identity, PostgreSQL users/memberships, role matrix, endpoint/error contracts, concurrency, browser storage/lifecycle, settings, tests, planned files, and rollout order.
- Defined additive revision `0002_auth_workspaces` after `0001_manual_records`; existing local-demo records, IDs, timestamps, decimal rules, and composite workspace ownership stay in place. No migration file was created or applied.
- Recorded source links to the official Cognito, oidc-client-ts, and PyJWT documentation after checking their provider/verification/storage behavior. These references support a design, not evidence of a working login.

Step 4.1 material decisions and integration conflicts:
- Replace the temporary fixed-demo dependency with membership verification on every business request; selection uses untrusted `X-Workspace-ID`. All roles read, administrators/accountants create, and only administrators manage memberships. Approval actions and designation remain deferred.
- `/me` registers only the verified caller's application-user row and returns their own ID even with no memberships. Subsequent workspace/membership operations use that application ID, never email. Workspace creation and its first administrator commit atomically; local removal retains an inactive identity tombstone.
- Missing/invalid credentials are 401 with a bearer challenge; inaccessible workspace selections and insufficient roles are 403; records/references outside an authorized workspace are 404; missing/malformed selections are 422. Explicitly reject workspace-selection headers on identity/workspace-management routes. Preserve sanitized errors and public health/readiness bodies.
- Serialize membership changes with workspace-row locks, reread caller authority after waiting, and reject loss of the last active administrator. Specify separate-connection concurrency tests and failure recovery.
- A first-demo-administrator CLI requires the configured verified issuer and copied subject from an already registered user. It grants no startup/email/public bootstrap access; current seeds continue to grant nothing.
- Current hash routing and numeric-host browsing need a dedicated query callback at `http://localhost:5173/auth/callback` and canonical localhost login origin. The logout return is `http://localhost:5173/`. Tokens remain in memory; only transient correlation state may use sessionStorage. Reload may require a new login redirect and loses unsaved drafts.
- Current TestClient fixtures and live demo HTTP reads are unauthenticated. Plan generated signing keys, the real verifier, database memberships, and a separate disposable HTTP-server harness without any production bypass or AWS calls. Preserve repeated seeding, live snapshots across restart, and public dependency outage/recovery checks.
- The previous PR #2 merge/synchronize task is retained above as historical handoff, not marked complete or remotely verified. The current request authorizes this documentation checkpoint; no Git integration action was taken. The temporary demo-access/no-frontend-dependency assumptions in the Step 3 blueprint are explicitly superseded; first-release scope is unchanged.

Step 4.1 checks actually performed:
- Initial Git status showed only pre-existing untracked `Microsoft/`.
- Documentation coverage check passed for ten groups covering the requested identity, schema, APIs, roles, error/selection rules, concurrency/removal, operator/data-retention, public/no-bypass, browser/lifecycle, and offline-test/settings/rollout contracts. All eleven numbered sections are present and ordered.
- Both changed documents passed trailing-whitespace, final-newline, and balanced-code-fence checks. The one illustrative PowerShell block parsed successfully without execution; source-link URL syntax passed.
- `git diff --check` passed; final tracked/untracked change-scope review is limited to the two requested documentation files plus pre-existing `Microsoft/`.

Step 4.1 validation limits and preserved boundaries:
- No application tests, frontend lint/build, Docker/Compose/checker commands, migrations, seeds, operator grants, API/SQL requests, browser login, AWS account actions, or GitHub CI were run. Historical Milestone 3 passes above were not rerun for Step 4.1.
- No application code, dependency/lockfile, infrastructure, applied migration, or database data was changed. Actual local environment files were not read, created, modified, or printed. `Microsoft/` remains untouched. No commit or push was performed.
- Authentication, new models/migration/endpoints, dependencies/settings, browser flows, CLI, and test/checker changes are planned only; Step 4.1 stops after documentation.

Step 4.3 implementation and file purposes (2026-10-17; Windows host PowerShell, Python/Alembic/pytest inside Linux containers):
- Read `AGENTS.md`, scope, progress, and the authentication contract before editing. Inspected existing models, initial migration, sessions, workspace/demo initialization, isolated PostgreSQL fixtures/schema tests, checker, CI, Compose, Docker packaging, and the tracked settings template. Initial Git status showed only pre-existing untracked `Microsoft/`.
- Explained every planned file and its purpose before editing, including the additional committed-fixture change before making it.
- Added `backend/app/models/application_user.py` and `workspace_membership.py`; registered them in `models/__init__.py` and added a read-only workspace membership collection in `models/workspace.py`. Users have exact issuer/subject uniqueness, active status, and UTC creation/update timestamps. Memberships have role checks, restrictive foreign keys, workspace/user uniqueness, and query indexes. All constraints and indexes are named.
- Added schema-only `backend/migrations/versions/0002_auth_workspaces.py`, following `0001_manual_records`. It creates the two tables and no data. Existing workspace/business tables and the applied initial revision are unchanged.
- Added `backend/app/cognito.py`: validate `COGNITO_REGION` and matching `COGNITO_USER_POOL_ID`, then derive the original regional issuer without discovery or AWS calls. Added only public identifier placeholders to `.env.example`; passed them through `compose.yaml` with empty defaults, preserving existing API startup. Extended `backend/.dockerignore` so environment files cannot enter the build context.
- Added `backend/app/services/identity.py`: insert-or-find the exact identity using PostgreSQL conflict handling, without normalization, commit, rollback, or reactivation. Added `services/memberships.py`: trusted add/read/list/change/remove operations, workspace-then-user locking, post-lock refresh, exact role validation, idempotent identical assignments, explicit role-conflict errors, and active last-administrator protection. No public router calls these services.
- Added `backend/app/bootstrap_membership.py`: explicit required subject/workspace-slug/role arguments, trusted derived issuer, existing workspace required, identity creation if needed, one commit or full rollback, harmless same-role repeat, refusal to replace a different role, and sanitized output/argument failures. No startup/import/seed/public-endpoint invocation was added.
- Added `backend/tests/test_cognito.py`, `test_membership_persistence.py`, `test_bootstrap_membership.py`, and `test_auth_migration.py` for synthetic configuration, real persistence/constraints/relationships, transaction ownership, rollback/recovery, actual module-command execution, separate-connection lock races, and populated-upgrade preservation.
- Extended `backend/tests/conftest.py` with a marker-guarded committed fixture whose cleanup deletes only known synthetic workspace/user rows. Existing savepoint fixtures remain intact. Updated `test_postgres_schema.py` for ten tables and the new head, strengthening its empty-database guard. Updated `test_seed_demo.py` to retain its original eight-table fixture checks and explicitly verify no identities/memberships are seeded.
- Updated README with current scope, configuration, exact PowerShell/Linux-container commands, transaction/concurrency explanations, test results, and limits. Updated `docs/auth-workspaces.md` to record the requested bootstrap/configuration changes and current intermediate behavior. Updated this progress record. Existing checker and CI already collect the new tests and needed no changes.

Step 4.3 decisions and differences from Step 4.1:
- The requested command is `python -m app.bootstrap_membership --subject SUBJECT --workspace-slug local-demo --role administrator`. Unlike the earlier plan, it may create the identity before any login or `/me`, may explicitly add further users/roles, selects an existing workspace by exact slug, and accepts no issuer override. The operator must obtain the intended subject from the chosen Cognito pool through a trusted channel; the command deliberately makes no AWS call to confirm it.
- Region/pool configuration replaces the earlier direct backend issuer setting for derivation. The current profile is the original regional Cognito issuer; updated/multi-region issuer profiles need a later reviewed configuration contract. No client secret, AWS credential, client ID setting, token library, or frontend setting was introduced.
- Persistence helpers do not own transaction completion or HTTP authorization. The bootstrap wrapper owns one commit/rollback. Future routers must verify the caller after acquiring the workspace lock; token verification and protected routes are deliberately not implemented in this checkpoint.
- A workspace row lock serializes every membership mutation. READ COMMITTED and fresh post-lock queries see competing commits before counting active administrators. Concurrent removal/demotion cannot remove the final active administrator. A three-second lock timeout requires rollback; a later operation can recover. Direct SQL is outside this service protocol, and no user-deactivation tool is added.
- Existing local-demo IDs, records, timestamps, exact decimal values, business rules, fixed-workspace request dependency, API errors/OpenAPI, seeds, health/readiness bodies, and frontend behavior remain unchanged. Membership persistence does not yet enforce API permissions. This completes only the explicitly requested Step 4.3; no other Milestone 4 step is claimed complete.

Step 4.3 checks actually performed:
- `.\scripts\check-backend.ps1` passed on its first run, exit code 0, using disposable project `supplier-invoice-verification-check-e8389591bcc64a6f8bbeda6b9f192710`. Compose configuration, locked image build, bounded startup, guarded database preparation, migration upgrade/current/head verification all passed; revision is `0002_auth_workspaces (head)` in that disposable database.
- Opted-in Linux-container pytest passed: 593 tests, no failures or skips (162 ordinary checks and 431 PostgreSQL integration cases). Named schema/metadata agreement, identity uniqueness and concurrent registration, membership FKs/relationships/roles, CLI repeat/conflict/missing workspace/inactive identity, transaction ownership, rollback/commit-failure recovery, and all retained tests passed.
- Separate-connection tests observed actual PostgreSQL lock waits before committing the first change. Concurrent remove/remove, demote/demote, remove/demote, and demote/remove retained one active administrator; competing bootstrap role assignments preserved the first role. Lock timeout/rollback/later success also passed.
- The actual `python -m app.bootstrap_membership` subprocess ran in the guarded test database with synthetic pool/subject values: first success persisted, identical repeat preserved the full access snapshot, and a different role exited nonzero without changes. No live AWS account, key, credential, or request was used.
- A guarded populated migration test downgraded only the disposable schema to `0001_manual_records`, inserted the full synthetic eight-table workflow plus another workspace/supplier, upgraded twice, and compared every existing row/ID/timestamp/value unchanged. New user/membership tables remained empty. It deleted only its own known rows and restored head; the retained guarded full downgrade/upgrade test also passed.
- Existing workspace initialization twice, full demo seeding twice, live HTTP detail/list/filter snapshots, API/PostgreSQL restart with volume retained, and identical post-restart records all passed. Public health/readiness returned 200 before migrations, health stayed 200 while readiness returned 503 with both dependencies stopped, and readiness recovered to 200 after restart.
- Ordinary pytest in the final built image with Docker networking disabled passed: 162 tests, 431 explicit PostgreSQL opt-in skips, exit code 0. Both pytest runs reported the existing unsuppressed Starlette TestClient/httpx deprecation warning; no unrelated dependency change was made.
- Verified the disposable project's containers, network, volume, and generated synthetic settings file were removed. Before/after Docker metadata showed the original development API still running and PostgreSQL/Redis healthy. No development API/SQL/migration/bootstrap operation was performed.
- All 24 PowerShell blocks across README/authentication documentation parsed without execution; checker PowerShell syntax passed. `git diff --check`, documentation/new-file whitespace checks, and final change-scope review passed. Git comparison confirmed `0001_manual_records.py`, sessions, main/routers, business services, seed commands, dependencies/lockfiles, Dockerfile, CI override, checker/CI, complete frontend, instructions, scope, and manual blueprint unchanged.

Step 4.3 user-run next commands and remaining limits:
- Set `$env:COGNITO_REGION = 'YOUR_REGION'` and `$env:COGNITO_USER_POOL_ID = 'YOUR_USER_POOL_ID'` in the same Windows PowerShell session, replacing placeholders with the intended existing pool. Copy that person's real Cognito subject separately; use no email lookup. No Cognito settings are needed for disposable tests or current API startup.
- From the project root in Windows PowerShell: `docker compose up --build -d api`, then `docker compose exec -T api alembic upgrade head`, then `docker compose exec -T api alembic current`. These are deliberate user-run development writes, not commands run by Codex. Expect `0002_auth_workspaces (head)`; retain the existing volume.
- Once `local-demo` exists, run `docker compose exec -T api python -m app.bootstrap_membership --subject 'COPIED_COGNITO_SUB' --workspace-slug local-demo --role administrator`; repeat the same command for the harmless-repeat check. If the workspace has never been initialized, explicitly run `docker compose exec -T api python -m app.seed_workspace` first. Python/Alembic run inside the Linux API container. README has the complete copyable command blocks and conflict behavior.
- Repeat isolated verification with `.\scripts\check-backend.ps1`. Online GitHub CI has not run on this uncommitted revision; frontend tests/lint/build were not repeated because frontend files are unchanged. No browser or real Cognito login was exercised.
- Actual local environment files were not read, created, modified, or printed. Only the explicitly authorized tracked `.env.example` template changed; the retained checker generated and removed its own synthetic disposable settings file. `Microsoft/` remains untouched. No commit or push was performed, and the development database was not migrated, seeded, reset, or granted memberships by Codex.
- Token verification, protected business routes, public membership/workspace APIs, frontend login, approval, and new AWS resources remain deferred. Current unauthenticated API behavior is preserved as requested; the existing dependency warning and unverified online CI remain recorded limits.

Step 4.3 user verification:
- Disposable backend checker passed with exit code 0.
- Development migration applied: 0002_auth_workspaces (head).
- Explicit administrator bootstrap succeeded for local-demo.
- Repeated bootstrap returned the same application-user ID and membership.
- API authentication and protected routes remain deferred to Step 4.4.

Step 4.4 implementation and file purposes (2026-10-17; Windows host PowerShell, backend checks in Linux containers):
- Read `AGENTS.md`, scope, progress, and the authentication contract first. Inspected Cognito derivation, identity/membership services, all business routers, sessions, error envelopes, tests, HTTP checkers, Compose, PowerShell orchestration, and CI. Explained planned files and purposes before editing. Initial status contained only pre-existing untracked `Microsoft/`.
- Added `backend/app/auth.py`: real RS256 access-token verification, immutable verified issuer/subject, strict bearer parsing, configured-only JWKS retrieval, async bounded streaming, public-key validation, cache/rotation/throttling, and separate invalid-credential/key-unavailable failures. Extended `app/cognito.py` with validated app-client configuration and derived JWKS URL.
- Added `app/api/authorization.py`: authenticate before JSON/query validation, resolve active identity by verified issuer/subject, enforce selector syntax and current PostgreSQL membership/role, and share one request session. Membership mutations acquire the workspace lock and reread caller authority after waiting. Updated `api/dependencies.py` to return that authorized user/workspace/session instead of the fixed demo workspace.
- Updated `api/errors.py` and `schemas/errors.py`: preserve sanitized envelopes, add 401/403 and bearer challenge, protect all existing business routes through their shared route class, expose bearer security in OpenAPI, and apply `no-store`. No changes to the four business router source files or their scoped business services were necessary.
- Added `api/me.py`, `workspaces.py`, `memberships.py`, and matching `schemas/identity.py`, `workspace.py`, `membership.py`. `/me` registers only the verified caller and returns their own ID/memberships. Workspace discovery/counts are scoped; membership administration uses existing application-user UUIDs. Added `services/workspaces.py` for atomic workspace/first-administrator creation and scoped discovery. Membership API wrappers own commit/rollback and reuse the existing last-administrator service protocol.
- Updated `app/main.py` with an application factory and startup-validated production verifier. `/health`, `/ready`, `/docs`, and `/openapi.json` remain public; health/readiness bodies are unchanged. Updated `backend/Dockerfile` to disable Uvicorn access logs, avoiding sensitive query-string logging.
- Updated `backend/pyproject.toml` and reproducibly regenerated `uv.lock`: added `PyJWT[crypto]>=2.10,<3.0`, moved existing HTTPX from development-only to runtime, retained all 38 existing package versions. New locked packages: PyJWT 2.15.1, cryptography 50.0.2, cffi 2.1.1, pycparser 3.11. Used uv 0.8.22 and Python 3.12.14 in the lock-generator Linux container; locked image builds passed.
- Updated only the tracked `.env.example` public placeholders and `compose.yaml` app-client pass-through. No issuer/JWKS override or auth-disable switch exists. Normal API host binding remains loopback and the named database volume is unchanged. `compose.ci.yaml` alone selects the guarded synthetic HTTP harness and literal fictional Cognito settings.
- Added `tests/__init__.py`, `auth_helpers.py`, and `run_http_api.py`: generated RSA keys, controlled public JWKS, signed fixture requests, and the separate guarded disposable HTTP-server entrypoint. Added `test_auth.py`, `test_authorization.py`, and `test_workspace_api.py` for signature/claim/cache/transport failures, roles/scoping/removals, caller-authority races, registration, and workspace atomicity/recovery.
- Updated `tests/conftest.py` to inject real generated-key verification and retain guarded session isolation; grants are explicit fixture actions. Adapted `test_manual_records.py`, `test_delivery_invoice.py`, `test_seed_demo.py`, `test_health.py`, `test_openapi.py`, and `test_check_demo.py` to authenticated requests or the application factory. Existing PostgreSQL schema, migration, CLI, identity-uniqueness, last-administrator race, and populated-record preservation tests remain collected unchanged.
- Added guarded `backend/scripts/check_auth.py` for signed `/me`, explicit operator bootstrap, real HTTP 401/403/404 checks, workspace discovery/creation, and persisted access after restart. Updated `check_demo.py` and `check_endpoints.py` to send optional headers while leaving public probes unauthenticated. Updated `scripts/check-backend.ps1` and `.github/workflows/ci.yml` to run authenticated checks before/after restart; retained migrations, repeat seeding, full snapshots, dependency outage/recovery, cleanup, and read-only CI permissions. Added `feat/auth-workspaces` to CI push branches; the frontend job is unchanged.
- Updated README with configuration, exact commands, endpoint/role/error/cache behavior, test isolation, rollout limits, and the Step 4.5 frontend dependency. Updated `docs/auth-workspaces.md` implementation status and actual paths/settings while retaining historical design evidence. Updated this progress record.

Step 4.4 decisions and review findings:
- The requested backend setting is `COGNITO_APP_CLIENT_ID`; it replaces the earlier contract draft's `COGNITO_CLIENT_ID` name. Region/pool remain the only source of the trusted original regional issuer/JWKS URL. No AWS IAM credentials or client secret are needed by the API. Missing/malformed settings fail startup without making an AWS call.
- Retained the reviewed unbound Cognito access-token profile: exact issuer/client, RS256 only, required subject/expiry/issued-at/purpose, 30-second time leeway, and rejection of any `aud` claim. Resource-bound tokens or updated/multi-region issuers require a separately reviewed contract; token-supplied key URLs never control requests.
- JWKS handling has a three-second total bound including lock wait and response body, 64 KiB cap, at most 20 public RSA keys, five-minute cache, and 30-second refresh throttling. Known unexpired cached keys can verify during an outage; expired keys cannot. An unknown key after successful retrieval is 401; failed required retrieval is 503. Rotation during the throttle interval may require waiting up to 30 seconds. No database permission cache exists.
- A route boundary is required for 401/403 precedence over malformed JSON and query validation; an ordinary FastAPI dependency would run too late for early body parsing. It retains the existing session generator's rollback/close semantics and never performs an unauthenticated payload lookup. Missing/malformed/duplicate business selection is 422; inaccessible workspace selection is 403; inaccessible scoped records/references are 404. Non-business account/membership routes reject the selection header with 422.
- During review, changed membership POST to check target activity before reporting an existing assignment. An inactive target now consistently returns 404. Added signed unknown-key-versus-outage and unsafe-test-harness/signing guard cases. Added deeply nested JSON and infinite timestamp regression cases; the locked PyJWT already rejects them as invalid credentials, requiring no verifier change.
- Existing Step 4.3 persistence and concurrency protocol is sufficient; no migration, model, session module, identity/membership persistence service, seed command, or business rule changed. The initial migration and all existing record/workspace IDs remain intact. The user's recorded development migration/bootstrap above is preserved and was not rerun by Codex.
- `/me` is the only ordinary first-registration endpoint; a verified new user gets their own application UUID and no memberships. Other endpoints return 403 until that registration. An operator may still explicitly provision through the existing CLI. No automatic `local-demo` access, email grant, public bootstrap/token-minting endpoint, or startup data write exists.
- Committed role/removal/active-status changes affect the next API request with the same JWT. Logout alone does not immediately invalidate an issued JWT to an offline verifier. No user-deactivation API/tool was added. Approval remains deferred.

Step 4.4 checks actually performed:
- The final `.\scripts\check-backend.ps1` run passed, exit code 0, using disposable project `supplier-invoice-verification-check-21d58c05a7aa456593228f4b72adabc2`. Compose validation, locked image build, bounded startup, guarded PostgreSQL preparation, migrations, and head verification passed at `0002_auth_workspaces (head)`.
- Final opted-in Linux-container pytest: **684 passed**, no failures or skips, in 44.17 seconds. Real generated-key signatures, malformed/expired/issuer/client/purpose/algorithm claims, rotation/outage/cache/deadline behavior, role matrix, cross-workspace records/references/counts, immediate role/removal/inactive denial, last-administrator races, caller demotion while waiting for the workspace lock, registration, and atomic workspace failure/recovery passed. All retained persistence/migration/seed/business tests passed, including populated-upgrade preservation.
- Actual signed HTTP `/me` registration and the explicit bootstrap command passed. Workspace initialization twice and demo seed twice preserved all returned detail/list/filter snapshots. Absent/forged credentials returned 401, a signed non-member received 403, and cross-workspace/missing scoped records returned 404. Workspace/identity access and identical business snapshots remained valid after API/PostgreSQL restart with the volume retained.
- Public health/readiness passed before migrations. During PostgreSQL/Redis outage, health stayed 200 and readiness returned its original 503 body; both recovered to their expected 200 bodies. Final cleanup removed that disposable project's containers, network, and database volume; temporary signing keys lived only inside the removed API container.
- Final metadata-only checks confirmed all three Step 4.4 disposable projects have no remaining containers, volumes, networks, or generated temporary settings files. The original development API was still running and PostgreSQL/Redis remained healthy. No development API, SQL, migration, seed, or bootstrap command was run.
- Earlier complete checker runs also passed: 676 tests in project `supplier-invoice-verification-check-cf352807215a48e7848d543b078a85e0`, then 679 tests after review changes in `supplier-invoice-verification-check-28ff926a11794119b0f5e0febbb47519`. The last five tests add malformed-token regression cases. The focused offline malformed-token selection passed 21 cases before the final full run; it required no production-code change.
- Ordinary pytest in the final built image with `docker run --rm --network none --entrypoint pytest supplier-invoice-verification-check-21d58c05a7aa456593228f4b72adabc2-api:latest -q` passed: **222 passed, 462 explicit PostgreSQL opt-in skips**, exit code 0. No mounted development data or network was available. Full and offline runs reported the existing unsuppressed Starlette TestClient/httpx deprecation warning.
- Unchanged frontend checks passed from Windows host PowerShell: `npm.cmd test` (**140 passed**, no failures/skips), `npm.cmd run lint`, and `npm.cmd run build` (TypeScript/Vite production build). No frontend source or dependency files changed.
- GitHub workflow validation passed with cached `rhysd/actionlint:1.7.12`, networking disabled and only the workflow directory mounted read-only. This is local syntax/static validation, not an online Actions run.
- Lockfile comparison against Git confirmed all 38 old package versions unchanged and exactly four new locked packages. PowerShell checker syntax and all 29 PowerShell blocks across README/authentication/progress documentation parsed without execution; documentation code fences are balanced. `git diff --check` and changed/new-file trailing-whitespace/final-newline checks passed. Scope comparison confirmed migrations/models, session module, existing identity/membership and business services, business routers, seed commands, frontend, instructions, scope, and manual blueprint unchanged.

Step 4.4 user configuration and exact next commands:
- The API now requires `COGNITO_REGION`, matching `COGNITO_USER_POOL_ID`, and `COGNITO_APP_CLIENT_ID` for the intended existing Cognito user pool/public browser app client. README contains complete PowerShell blocks and a non-echoing in-memory access-token prompt; no real token is needed for isolated verification.
- To repeat isolated verification from Windows host PowerShell at the repository root: `.\scripts\check-backend.ps1`. It uses only generated synthetic disposable settings and Linux containers, and never targets the development database.
- To start the development API deliberately, set `$env:COGNITO_REGION = 'YOUR_REGION'`, `$env:COGNITO_USER_POOL_ID = 'YOUR_USER_POOL_ID'`, and `$env:COGNITO_APP_CLIENT_ID = 'YOUR_PUBLIC_APP_CLIENT_ID'`, replacing all placeholders in the same PowerShell session; then run `docker compose up --build -d api`. Public checks: `Invoke-RestMethod 'http://127.0.0.1:8000/health'` and `Invoke-RestMethod 'http://127.0.0.1:8000/ready'`. These development commands were documented, not run by Codex. No new migration is required after the user's recorded `0002_auth_workspaces (head)`.
- Only if deliberately granting another verified subject: `docker compose exec -T api python -m app.bootstrap_membership --subject 'COPIED_COGNITO_SUB' --workspace-slug local-demo --role administrator`. Obtain the subject from the trusted configured pool; never use an unverified decode or email. The user's earlier grant is not repeated automatically.
- Frontend checks from Windows host PowerShell: `Set-Location frontend`, `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`. Browser business pages require separately requested Step 4.5 login/token/workspace integration; public Status works now.

Step 4.4 user verification:
- Development API rebuilt with the configured Cognito pool and app client.
- Database revision remains 0002_auth_workspaces (head).
- Public /health and /ready returned healthy responses.
- Anonymous /me and /suppliers requests returned HTTP 401 with sanitized errors.
- Actual .env remains ignored by Git.
- Real Cognito login and authenticated browser requests remain pending.

Step 4.4 remaining limits at that checkpoint: real Cognito/browser flow and online GitHub CI remained unverified; frontend login/protected headers were still pending. The existing backend TestClient deprecation warning remained. No development database or AWS resources, actual local environment files, or `Microsoft/` were changed by Codex; no commit or push was performed.

Step 4.5 implementation and file purposes (2026-10-17; Windows host PowerShell, Node.js 24.21.0/npm 11.19.0):
- Read `AGENTS.md`, scope, authentication contract, and progress before editing. Inspected actual backend API/schema contracts and frontend pages, hash navigation, request scopes/hooks, selection helpers, decimal validation, tests, Vite, ignore rules, and package lock. Initial status contained only pre-existing untracked `Microsoft/`. Explained planned files and purposes before editing.
- Added `frontend/.env.example` with only the five requested public placeholders. Added `src/authConfig.ts` for validated original regional issuer, public client, HTTPS managed-login domain, and exact local callback/logout URLs; failures yield setup guidance and leave Status usable. Existing root ignore rules already ignore `frontend/.env.local` and allow the example, so no ignore-file change was necessary.
- Added `src/auth.ts`: `oidc-client-ts` code-flow/PKCE/nonce integration, pinned discovery endpoints, explicit in-memory user store, dedicated sessionStorage correlation state, callback protocol validation, refresh-token-only renewal, bounded refresh-token revocation, and Cognito logout URL. Logging is disabled. No localStorage token store, iframe renewal fallback, secret, raw provider error, or token display was added.
- Added `src/session.ts`: identity/workspace state outside React, one callback bootstrap promise, login/renewal generation guards, coalesced renewal/expiry handling, verified `/me` identity comparison, accessible memberships/selection, permission refresh, cancellation/cleanup, uncertain-write notices, and conditional logout navigation. Each invalidated client has its own discarded memory store so a late library completion cannot restore the current session.
- Added `src/authRuntime.ts` and `authContext.tsx`; updated `main.tsx` to start callback handling before mounting React/StrictMode. Runtime reads only the five explicit public build variables; it strips callback query data before asynchronous processing, listens for cancelled navigation/Back restoration, and clears old sessions on Vite hot replacement. Added `authTypes.ts` for actual identity/workspace/membership contracts and UI permission policies.
- Added `src/accountApi.ts` for `/me`, atomic workspace creation, and path-scoped membership list/add/change/remove. It validates fields/responses, uses existing application-user UUIDs, rejects email grants, and does not send `X-Workspace-ID` on these APIs. `/me` already supplies the full accessible workspace objects/roles, so the selector uses that response rather than fetching a redundant/global directory. Backend behavior remains authoritative and unchanged.
- Updated `src/api.ts`: same-origin access bearer, business-only selected workspace, omitted cookies, rejected redirects, current-context transport cancellation and completion guards, distinct 401/403 handling, validated workspace responses, and PATCH/DELETE/204 support. Retained decimal strings, payload filtering, error envelopes, full-body request bounds and no automatic write retry. Uncertain-write tracking survives a timeout followed by a workspace switch.
- Updated `src/requestScope.ts` and `hooks/useBusiness.ts` to include context generation in read keys/completion checks as well as navigation cancellation; existing `useSelectedOrder` and selection/validation helpers remain unchanged. Updated `components/RequestState.tsx` and `FormFeedback.tsx` with clear auth/conflict messaging and same-tab record verification links, since a new tab intentionally lacks in-memory login.
- Added `pages/SignInPage.tsx`, `AccountPage.tsx`, `WorkspaceNewPage.tsx`, `MembershipsPage.tsx`, and `components/WorkspaceSelector.tsx`. They provide setup/sign-in/cancel, own application-user ID/copy/onboarding, explicit atomic workspace creation, accessible selection/current role, and administrator existing-user-ID membership changes with conflict/last-admin guidance and explicit list refresh. No automatic demo grant or approval action exists.
- Updated `src/App.tsx`, `components/Navigation.tsx`, and `App.css` for session gates, public Status, per-context remount/cleanup, account/member navigation, workspace/warning display and accessible layout. Updated supplier list/detail, purchase-order list, delivery list, and invoice list pages to hide business creation links for approvers. Direct create routes are also gated; administrator/accountant forms keep existing deterministic behavior. Workspace-scoped business drafts remain mounted across ordinary page/account/status navigation; context changes clear them. Account/admin forms are page-local.
- Updated `vite.config.ts` to bind only the loopback address resolved for `localhost`, preserve strict port 5173 and proxy target `http://127.0.0.1:8000`, and use `envDir: false` only when `SIV_NO_ENV_FILES=1`. This verification option disables file loading, not authentication; explicit public process variables still work.
- Added `oidc-client-ts` 3.5.0 and its transitive `jwt-decode` 4.0.0 to `package.json`/`package-lock.json`; all 185 existing package versions are unchanged. The first sandboxed npm attempt was denied registry/cache access; the authorized elevated retry installed and locked the two packages. No other dependency was added.
- Added `tests/auth-fixtures.mjs`, `auth.test.mjs`, `workspaces.test.mjs`, and `ui.test.mjs`. These use the real library with synthetic discovery/token responses, lifecycle/request failure fixtures, rendered React permission/onboarding controls, and a short-lived actual localhost Vite server with environment-file loading disabled. Updated existing API/delivery-invoice tests to supply explicit authenticated fixtures and status tests to assert no private headers. Preserved all prior business/navigation/validation/status cases.
- Updated README with exact public settings/process-only startup/check commands, lifecycle tradeoffs, user-driven browser verification, and scope limits. Updated `docs/auth-workspaces.md` with Step 4.5 status, actual frontend paths, and the requested setting-name changes. Updated this progress record.

Step 4.5 decisions and limits:
- User-requested `VITE_COGNITO_AUTHORITY`, `VITE_AUTH_CALLBACK_URL`, and `VITE_AUTH_LOGOUT_URL` replace the earlier design's issuer/redirect/logout names. This checkpoint accepts only `http://localhost:5173/auth/callback` and `http://localhost:5173/`; callback hash fragments and numeric-host login are rejected. Original regional issuer support matches the unchanged backend; no deployment/multi-region issuer work was added.
- Library `OidcClient.createSigninRequest` generates and stores code/state/PKCE/nonce; `UserManager.signinRedirectCallback` validates the response. The coordinator performs external navigation only after checking its generation, so an abandoned asynchronous login cannot redirect later. Callback bootstrap is outside React and coalesced. URLs are stripped immediately, state expires after 15 minutes, cancellation/denial/replay do not automatically retry, and return routes must be known internal hashes.
- Explicit library memory storage holds access/ID/refresh tokens. Only PKCE/state/nonce and a validated return route use dedicated transient sessionStorage. Browser reload, a new tab, or Vite replacement may require a new explicit login redirect and lose unsaved forms. This is deliberate; there is no token persistence or production bypass.
- Refresh-token renewal runs 60 seconds before expiry and is rechecked before dispatch after a suspended tab resumes. It is coalesced, bounded to ten seconds, and never uses an iframe. Failed/missing refresh, timeout, changed identity, or inadequate new expiry clears the session. A request timing out before renewal completes cannot dispatch later. No POST/PATCH/DELETE is automatically replayed.
- Logout clears shared identity/selection/forms/records/private requests before bounded best-effort revocation of the refresh token alone, followed by Cognito `/logout?client_id=...&logout_uri=...`. Leaving cancels a late logout redirect. Local cleanup remains effective during provider failure. Already issued JWTs may remain accepted by the offline verifier until expiry; current database membership/active status is still checked on the next API request.
- 401 ends local authentication; 403 keeps it and refreshes `/me`, clearing previous private context and controls; 503 offers recovery. Backend roles and permissions remain authoritative. A known 401/403 denial does not generate a false uncertain-write warning. A dispatched timeout/interruption can leave a committed write: warnings stay associated with the original workspace across selection changes, and no automatic resubmission occurs.
- Synthetic ID-token fixtures test the library's code/state/nonce/refresh protocol behavior; they do not prove provider JWT signatures or real Cognito acceptance. Backend real-signature tests remain the separately recorded Step 4.4 evidence. Rendered component tests and actual localhost SPA serving are also separate from an interactive browser/managed-login check.
- No backend source, schema, migration, data, dependency/lockfile, Compose, infrastructure, HTTP checker, PowerShell checker, or CI workflow change is needed. No development API/SQL/migration/seed/bootstrap call, AWS resource action, actual local environment-file access, commit, or push was performed. `Microsoft/` remains untouched.

Step 4.5 checks actually performed:
- `npm.cmd ci --no-audit --no-fund --offline` passed from the existing npm cache after locking the dependency, exit code 0; a clean install added 162 packages for this platform. Lock comparison preserved all 185 prior package versions and added only `oidc-client-ts` 3.5.0 and `jwt-decode` 4.0.0.
- Final `npm.cmd test` after that clean install passed: **217 tests**, no failures, cancellations or skips, exit code 0 (2.78 seconds reported by Node). This includes all 140 pre-existing cases plus 77 new authentication/workspace/rendered-UI cases. No AWS account, credential, live token, actual environment file, development API call, or database was used.
- The real installed library generated S256 PKCE/verifier, nonce and correlation state, consumed a callback once, rejected replay/mismatched state/nonce/denial/expired transient state, used the refresh-token grant with rotation, rejected missing refresh before any iframe/network request, confined a late completion to its discarded store, and revoked only the newest refresh token after cleanup. Synthetic discovery/token responses were controlled fetch fixtures; no real provider acceptance or browser JWT-signature proof is claimed.
- Session/request tests passed for callback coalescing and cancellation including during `/me`, safe internal return navigation, numeric-host refusal, missing-config guidance, no-membership onboarding and own ID, multiple workspace choice, current auth headers, no selection header on account/member APIs, 401 cleanup, 403 role refresh, membership loss, 503 recovery, clear 409 conflicts, coalesced/failed/timed-out/changed-subject renewal, logout during renewal, stale identity/read/write responses, context generation, uncertain-write retention, and no late dispatch/replay after renewal.
- Vite/React tests loaded only explicit configuration with `envDir: false`, bound an ephemeral server to the actual localhost loopback address, received HTTP 200 SPA responses at `/` and query `/auth/callback`, and closed that server. They asserted the unchanged API proxy target without calling it. Rendered read pages hid create links for approvers, navigation/account hid member management from non-admins, and onboarding/selector showed only synthetic accessible IDs/roles. These are static rendering and HTTP checks, not an interactive browser/Cognito run.
- `npm.cmd run lint` passed with no errors/warnings, exit code 0. Final `npm.cmd run build` passed TypeScript and Vite production build with `SIV_NO_ENV_FILES=1` and five explicit synthetic public process settings, exit code 0 (64 modules; JavaScript about 381 kB / 108 kB gzip). An earlier build with file loading disabled and missing settings also passed, exercising the build's useful-setup path without reading any actual environment file.
- Initial TypeScript validation caught response-validator narrowing errors and initial lint caught mutation of a hook argument; both were corrected before the final clean-install checks. Existing 140 tests passed during integration; the later 211-case suite and the final 217-case suite both passed. No test failure was suppressed.
- `git check-ignore --no-index frontend/.env.local` confirmed it remains ignored; the example returned the expected non-ignored result without reading either file's contents. Parsed all 31 PowerShell blocks across README/authentication/progress without execution; documentation fences, final newlines and trailing whitespace passed. `git diff --check` passed. Final scope checks contain only the frontend and three requested/related documents (24 tracked files plus 17 new frontend files).
- Git comparison confirmed the complete backend and its migrations/lockfile, Compose, CI, PowerShell/backend checkers, root settings template/ignore rules, scope/instructions/manual blueprint, and existing frontend decimal/selection/status logic unchanged. No backend test/checker or development database action was run for Step 4.5; Step 4.4 results above remain historical evidence. No actual local environment file or `Microsoft/` content was read or changed, and no commit/push or AWS action occurred.

Step 4.5 exact next user commands:
- From Windows host PowerShell at the repository root: `Set-Location frontend`, then `$env:SIV_NO_ENV_FILES = '1'`, `npm.cmd ci --no-audit --no-fund`, `npm.cmd test`, `npm.cmd run lint`, and `npm.cmd run build`. Tests/build need no actual environment file, AWS account, or live token. README has complete copyable blocks.
- For real browser verification, use the existing configured backend and set the five public `VITE_*` process settings in README, matching the same pool/client/domain and exact localhost URLs. Keep `SIV_NO_ENV_FILES=1` for a process-only setup; run `npm.cmd run dev` and open `http://localhost:5173/#/signin`. No new migration, seed, or automatic bootstrap is required.
- Deliberately verify login/callback/Back/denial/reload, own-ID/no-membership onboarding, chosen synthetic workspace/member creation, all three roles, conflict/last-admin errors, switch/removal/expiry/renewal failure, interrupted writes, logout and another identity. Browser-created identities/workspaces/memberships are explicit user database writes; none were made here. Do not copy/log tokens while checking storage/network behavior.

Step 4 user verification:
- Real Cognito login succeeded for both test accounts.
- First account accessed local-demo as administrator and loaded existing records.
- Second account initially had no workspace memberships.
- Second account created its own separate workspace with empty business lists.
- Explicit approver membership allowed reading demo records without creation controls.
- Changing the role to accountant enabled supplier creation.
- Removing demo membership prevented further access while preserving access to the second account's own workspace.
- Last-administrator protection behaved as expected.
- Logout cleared authenticated application state and required login for business access.
- The callback cancellation regression was corrected; Codex reported 218 frontend tests, lint, and build passing.
- GitHub push and pull-request backend/frontend checks passed for commit 2152ef0.

Next task:
- Merge pull request #3 after its latest checks pass and synchronize local main.
- Prepare the tools and skills required for Milestone 5 before implementation.

Step 4.5 login redirect correction:
- Traced the exact cancellation message to `BrowserSession.cancelPending` in `frontend/src/session.ts`. The Continue button invokes `session.signIn`; the runtime delegates external navigation to `window.location.assign`. There is no `beforeunload`/`pagehide` cancellation listener or unsaved-changes blocker in this implementation. Bootstrap runs outside React/StrictMode, and business-request cleanup does not call the authentication cancellation handler. Redirect exceptions use a different sanitized message.
- Confirmed the defect before changing application code with a synthetic callback and the runtime's event wiring: successful callback and `/me` completion called `host.replace`, whose internal `hashchange` reached `cancelPending` while `callbackActive` was still true. This cleared the newly established identity/membership and produced the user's exact cancellation message. The flag was previously cleared only in `finally`, after the synchronous event had already fired. This is a callback-return ordering defect, not evidence that normal document unloading cancelled the outbound provider request. No live provider redirect was observed.
- Changed only the callback completion branch in `frontend/src/session.ts`: clear its pending flag immediately before the guarded internal return navigation. Pending login/callback/logout cancellation, generation guards, PKCE/state/nonce validation, memory-only tokens, safe URL processing, and logout behavior remain intact.
- Added one regression in `frontend/tests/auth.test.mjs` using an EventTarget with the same synchronous `hashchange`/`cancelPending` wiring. It failed before the fix (`signed-out` instead of `ready`) and passed afterward, checking one internal return, retained user/workspace, and a subsequent authenticated API request. Existing genuinely cancelled callback/identity-load/sign-in/logout cases also passed.
- Checks actually run from Windows host PowerShell: focused regression failed as expected before the fix; the focused five-case callback/cancellation selection then passed; full `npm.cmd test` passed **218 tests**, no failures/skips; `npm.cmd run lint` passed; `npm.cmd run build` passed TypeScript/Vite. Tests/build disabled environment-file loading, and the build used only explicit synthetic public settings. No actual environment file, development API/database, AWS account/token/resource, or live Cognito browser session was accessed. This entry and the session/test files are the only changes made for this debug request; existing Step 4.5/unrelated changes are preserved. No commit or push.
- User verification: reload `http://localhost:5173/`, click **Sign in**, then **Continue to Cognito**, and complete login if prompted. On return, Account should retain the application-user ID and accessible workspaces instead of showing the cancellation message. An existing Cognito session may return immediately. Real Cognito/browser login remains unverified by Codex.

Remaining limits:
- Real Cognito login and core workspace/role workflows were verified by the user, as recorded above.
- Expiry/renewal failures and interrupted writes have automated coverage but were not manually verified with real Cognito.
- GitHub push and pull-request backend/frontend checks passed for commit 2152ef0.
- Approval, uploads, AI, exports, and deployment remain outside this milestone.
