# Progress

Current milestone: 3 - Manual business records
Current task: Step 3.1 - Repository inspection and manual workflow blueprint (in progress)

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

Next task:
- Review the Step 3.1 blueprint and its proposed decisions; Step 3.1 remains the current in-progress checkpoint.
- Await a separate requested implementation step before creating application files or changing database contents. Do not skip ahead to later milestones.

Blockers: None recorded.
