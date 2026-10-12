# Progress

Current milestone: 3 - Manual business records
Current task: Step 3.3 - supplier and purchase-order APIs (not started)

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

Next task:
- Commit the completed Step 3.2 implementation and verification record.
- Begin Step 3.3: demo workspace initialization, supplier APIs, and purchase-order APIs.
- Verify Milestone 3 on GitHub Actions after pushing the implementation.

Blockers: None recorded.
