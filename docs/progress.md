# Progress

Current milestone: 2 - Local foundation
Current task: Step 2C - automated checks (implemented; GitHub verification pending)

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
- GitHub CI: PENDING until the user verifies an online run; no commit, push, merge, deployment, or Step 3 work performed
- Direct frontend `npm ci` initially failed because Windows locked a native Vite module; a clean temporary install succeeded, and missing local dependencies were restored with matching native binaries
- The first real outage check timed out with a three-second per-request cap; allowing each HTTP request its remaining 60-second overall budget fixed the check, and the full backend rerun passed
- Pytest passed with one Starlette TestClient/httpx deprecation warning from the committed dependencies; lockfiles were not changed

Next task:
- User verifies the Step 2C workflow online before advancing; remain in Milestone 2

Blockers: None recorded.
