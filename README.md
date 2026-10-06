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
