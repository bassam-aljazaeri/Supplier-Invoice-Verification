# Supplier-Invoice-Verification

AI-assisted supplier invoice extraction, matching, review, and approval.

## Status
Local development status page is available. Invoice application features are
not implemented yet.

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
