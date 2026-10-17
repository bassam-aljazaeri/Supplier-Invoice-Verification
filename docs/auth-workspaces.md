# Authentication and workspace authorization contract

Step 4.1, 2026-10-17: repository inspection and documentation only. This is the
implementation contract for later Milestone 4 tasks, not a statement that
authentication is implemented. Only this document and `docs/progress.md` change
in this checkpoint. No application, dependency, infrastructure, migration, or
database changes are authorized by Step 4.1.

## 1. Inspected baseline and scope decisions

| Inspected area | Current behavior and consequence for implementation |
| --- | --- |
| `backend/app/db.py`, `main.py` | Synchronous SQLAlchemy sessions roll back on failure and close per request; services explicitly commit. Startup creates clients, not tables or seed rows. Preserve these transaction boundaries. |
| `backend/app/models/`, `backend/migrations/` | Eight application tables and applied revision `0001_manual_records`. Business headers and lines have workspace ownership and composite foreign keys. Add identity tables in a new revision. |
| `backend/app/api/dependencies.py`, `workspace.py` | `WorkspaceDependency` resolves the fixed demo UUID and checks its slug/name; missing/conflicting demo data returns 503. There is no authenticated caller or membership check. Replace this dependency for business requests. |
| Four business routers, `services/manual_records.py` | Twelve create/list/retrieve operations for suppliers, purchase orders, delivery receipts, and draft invoices. Reads, counts, filters, references, and writes already use a workspace ID; retain that scoping behind authorization. |
| `api/errors.py`, `schemas/errors.py` | Sanitized 422/404/409/503/500 envelopes. The route wrapper currently rejects `workspace_id` query parameters before running dependencies. Authentication must precede that validation in protected routes, and 401/403 must keep their status and headers through the wrapper. |
| `seed_workspace.py`, `seed_demo.py` | Explicit, repeatable insert-or-verify commands; no implicit startup writes. Neither grants permissions. Preserve fictional data, fixed IDs, conflict behavior, and atomic seeding. |
| `frontend/src/App.tsx`, `navigation.ts`, `components/Navigation.tsx` | Hash navigation, all business links/forms currently available without login, and drafts retained in React memory. Add authentication, workspace selection, and role-aware controls. |
| `frontend/src/api.ts`, hooks, `requestScope.ts`, `status.ts` | Native fetch through `/api`, five-second full-body bounds, cancellation and stale-completion guards, no automatic POST retry, and uncertain-write handling. Business requests currently send neither bearer token nor workspace header. Status requests are separate. |
| `frontend/vite.config.ts`, README | Vite binds to `127.0.0.1:5173` and proxies `/api` to port 8000. Current browsing instructions use the numeric host; authentication must use the canonical `localhost` origin below. |
| `backend/tests/conftest.py`, API/schema/seed tests | PostgreSQL 17 opt-in, project/database/user/marker guards, outer transactions and per-request savepoints. Current clients are unauthenticated. Retain guards and rollback isolation; update clients to sign real test JWTs. |
| `backend/scripts/check_schema.py`, `check_demo.py`, `check_endpoints.py`, `scripts/check-backend.ps1`, CI | Disposable migrations/tests, twice-run seeds, live HTTP record snapshots before/after API/PostgreSQL restart, then dependency outage/recovery. Business HTTP reads are currently unauthenticated and must gain credentials. |
| Dependency manifests and Dockerfile | Neither `oidc-client-ts` nor PyJWT is declared. The API image already includes application, tests, scripts, and migrations. Add and lock dependencies only in later implementation. |

The fixed workspace is currently local demo context, not company isolation.
This contract intentionally replaces that temporary Step 3 rule. It also
supersedes the manual blueprint's temporary assumption of no added frontend
dependency and no workspace selection. That blueprint remains historical.

The scope's administrator/accountant/approver roles are retained. Approver is a
read-only role for this milestone; approval actions, the one designated approver
rule, independent approval, uploads, extraction, discrepancy checks, export,
activity history, and cloud deployment remain deferred. Multiple read-only
approver memberships do not designate an invoice approver. EUR, exact decimal
calculations, business validation, and draft-only invoices retain their contracts.

The progress file previously named PR #2 merge/local synchronization as the next
task. This request authorizes Step 4.1 documentation now; no merge, branch
synchronization, commit, push, or claim about remote merge state is made here.
There is no conflict with the first-release business scope. The temporary demo
access, numeric browser origin, and unauthenticated checks are material
integration conflicts resolved explicitly by the decisions below.

## 2. Identity provider, browser flow, and API token verification

Use an Amazon Cognito **user pool** and a **public browser app client without a
client secret**. No identity pool, AWS SDK credentials, or AWS account keys are
needed by the browser or API. Provisioning a real pool/client/domain is a later
operator task, not an action in Step 4.1 or a CI requirement.

Use `oidc-client-ts` with Authorization Code Flow and PKCE using S256. Set
`response_type: "code"`, `response_mode: "query"`, and leave PKCE enabled.
Request `scope: "openid"`; email/profile are unnecessary for application identity.
Disable implicit and client-credentials grants for this browser client. Let the
library generate/check correlation state and the PKCE verifier; supply a fresh
cryptographically random nonce through its sign-in API and require its check.
These choices follow Cognito's [authorization endpoint contract](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html).

The browser sends only the **access token** as `Authorization: Bearer <token>`
to the API. ID tokens describe browser sign-in and must never authorize API
requests. Refresh tokens go only to Cognito's token/revocation endpoints.

Backend identity is the exact, case-sensitive **verified `(issuer, sub)` pair**.
Here `issuer` is the token's verified `iss`, and `subject` stores its verified
`sub`. Email, username, token groups, browser claims, and client-supplied user IDs
do not identify the caller or grant application roles. Never merge users because
emails match. The same subject under another issuer is a different identity;
changing a pool requires a separate reviewed identity migration.

### Verification boundary

Use PyJWT with its `cryptography` support (`PyJWT[crypto]`, locked later).
Every protected HTTP request must pass the same verifier before application
identity lookup or workspace access:

1. Require one well-formed bearer Authorization header. Reject missing, empty,
   duplicated, conflicting, or other authentication schemes with 401. Do not
   accept tokens in query strings, cookies, bodies, or alternate identity headers.
2. Accept only RS256 with a nonblank `kid` and an RSA signing key from the trusted
   pool's JWKS. Pin `algorithms=["RS256"]`; never derive allowed algorithms,
   issuer, or key URLs from the supplied token. Ignore token `jku`/`x5u` URLs.
3. Verify the signature, exact configured issuer, and required claims `iss`,
   `sub`, `exp`, `iat`, `token_use`, and `client_id`. Check numeric time claims,
   expiration, future issue time, and `nbf` when present, with 30 seconds of clock
   leeway. Require a nonblank bounded subject, `token_use == "access"`, and exact
   configured browser `client_id`. Never turn signature or expiry checks off.
4. This contract uses Cognito access tokens without resource binding. They use
   `client_id`, not the ID token's `aud`, for client validation. Require `aud` to
   be absent; a resource-bound access token is rejected until an explicit API
   audience contract is added. If PyJWT audience verification is disabled for
   this no-`aud` profile, the explicit absence and `client_id` checks are mandatory.

Cognito documents the token types and client claims in [JWT verification](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html).
PyJWT documents signature, issuer, time, and required-claim checks in its
[usage guide](https://pyjwt.readthedocs.io/en/stable/usage.html) and warns against
token-selected algorithms in its [API reference](https://pyjwt.readthedocs.io/en/latest/api.html).

Derive the sole JWKS URL from the configured issuer by appending
`/.well-known/jwks.json`. Use bounded HTTPS requests (three seconds total), no
redirects to other origins, and a per-process five-minute cache of public keys.
An unfamiliar `kid` permits one refresh, rate-limited per issuer to once per 30
seconds, including a short negative-result cache. Refreshed JWKS without that
key, malformed JWTs, wrong claims, and bad signatures return 401. A required key
fetch that fails or returns invalid JWKS returns sanitized 503, never acceptance.
A still-valid cached key can verify during a provider outage; an expired cache
cannot. Coalesce concurrent refreshes; test rotation and recovery.

Validate settings at server startup without network calls, database writes, or
mandatory eager JWKS loading. `/health` and `/ready` must not fetch Cognito
metadata, require a key cache, or depend on a user/membership. The API is an
offline signature verifier between key fetches; it does not call Cognito GetUser
or a token-introspection service for each request.

## 3. PostgreSQL identity and membership schema

Add two tables using the existing UUID and UTC timestamp conventions. Application
users are global identities; company access belongs only in membership rows.

| `application_users` field | Type, defaults, and constraints |
| --- | --- |
| `id` | UUID primary key, server `gen_random_uuid()`; the application-user ID shared with an administrator. |
| `created_at` | TIMESTAMPTZ NOT NULL, server `CURRENT_TIMESTAMP`. |
| `issuer` | VARCHAR(512) NOT NULL, trimmed/nonblank; exact configured issuer on creation, immutable. |
| `subject` | VARCHAR(255) NOT NULL, trimmed/nonblank; exact verified `sub`, immutable; never substitute email. |
| `is_active` | BOOLEAN NOT NULL DEFAULT true; looked up on every request, never taken from a token. |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `CURRENT_TIMESTAMP`; explicitly set on local status change. |

Name the identity uniqueness constraint
`uq_application_users_issuer_subject (issuer, subject)`, with named text checks
for issuer/subject and the normal named primary key. Do not normalize, lowercase,
or silently truncate identity claims. No email column, password, token, or
client secret is needed. API payloads cannot set identity/status fields.

| `workspace_memberships` field | Type, defaults, and constraints |
| --- | --- |
| `id` | UUID primary key, server `gen_random_uuid()`. |
| `created_at` | TIMESTAMPTZ NOT NULL, server `CURRENT_TIMESTAMP`. |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `CURRENT_TIMESTAMP`; set when role changes; a no-op role assignment preserves it. |
| `workspace_id` | UUID NOT NULL, named FK to `workspaces.id`, `ON DELETE RESTRICT`. |
| `application_user_id` | UUID NOT NULL, named FK to `application_users.id`, `ON DELETE RESTRICT`. |
| `role` | VARCHAR(16) NOT NULL, no default; named check permits exactly `administrator`, `accountant`, `approver`. |

Add `uq_workspace_memberships_workspace_user (workspace_id, application_user_id)`
and indexes `(application_user_id, workspace_id)` for caller memberships,
`(workspace_id, role)` for administrator counts, and
`(workspace_id, created_at, id)` for membership pagination. Use named constraints
consistently in ORM metadata and migration. One user has at most one role per
workspace, and may have different roles in different workspaces. There is no
global administrator role.

Add `backend/migrations/versions/0002_auth_workspaces.py`, revision
`0002_auth_workspaces`, `down_revision = "0001_manual_records"`. It creates only
the two tables, checks, foreign keys, and indexes. Add model imports to shared
metadata. It inserts no users/memberships and changes no business rows or existing
workspace columns. Never edit the applied `0001_manual_records.py`, reset a
database, change existing record IDs, or move records into a new workspace.

Existing fictional and manually entered records stay in `local-demo`, UUID
`00000000-0000-4000-8000-000000000001`. It initially has zero memberships after
upgrade and is inaccessible until the operator explicitly grants access. A
freshly created workspace also briefly has zero memberships inside its creation
transaction; it cannot become visible without its first administrator commit.
The last-administrator rule therefore applies to established membership sets,
not as an impossible row-level check during migration or creation.

A downgrade drops memberships before users and does not touch business tables.
It loses access assignments and must never be part of normal rollout/recovery.
Exercise downgrade only in the already guarded disposable migration tests.

## 4. Roles, workspace selection, and errors

| Operation within an accessible workspace | Administrator | Accountant | Approver |
| --- | --- | --- | --- |
| List/retrieve suppliers, orders, deliveries, draft invoices and their related records | Yes | Yes | Yes |
| Create these business records | Yes | Yes | No |
| List/add/change/remove workspace memberships | Yes | No | No |
| Approval, rejection, submission, export, or editing saved records | Deferred | Deferred | Deferred |

All active authenticated application users can call `/me`, list their own
workspaces, and create a new workspace, including users with no memberships.
Creating one makes the caller its first administrator; it grants no access to
any existing workspace. Browser-hidden controls improve usability; backend
checks enforce permission on every request.

### Workspace selection

All twelve existing business operations require exactly one `X-Workspace-ID`
header containing a canonical UUID. This is an **untrusted selection**, never
proof of access. Resolve the current active application user, then query that
user's membership for the selected workspace on every request. The database
membership supplies both the workspace ID and role used downstream. No fallback
to `local-demo`, first membership, route history, or a token's workspace claim.

Reject `workspace_id` in business query/body input as before. Never trust
`X-Role`, `X-User-ID`, `X-User-Email`, token groups, or any equivalent role/workspace
assertion. Such headers cannot elevate access. Membership-management routes use
their workspace path parameter instead of `X-Workspace-ID`; `/me` and collection
`/workspaces` routes need no selection. Reject any `X-Workspace-ID` on these
non-business routes with 422 to avoid two competing selectors.

Keep all record queries and reference validations constrained by the authorized
workspace, including nested lines, counts, filters, pickers, and writes. Do not
fetch an arbitrary record globally and then disclose its workspace. Existing
composite foreign keys remain the final guard on cross-workspace links.

### Status and response contract

Protected routes retain `{"error":{"code":...,"message":...,"details":[]}}`.
Add `unauthorized` and `forbidden` to the existing error-code schema. Auth errors
have constant messages and empty details. Keep tokens, unverified claims, SQL,
and raw provider diagnostics out of errors/logs; `/me` returns only its declared
verified identity fields. Return `Cache-Control: no-store` for
identity, membership, and protected business responses.

| Condition | Response |
| --- | --- |
| Missing/invalid credentials, expired token, wrong issuer/client/type/signature | 401 `unauthorized`, with `WWW-Authenticate: Bearer`. |
| Verified caller has no provisioned application row yet on an endpoint other than `/me` | 403 `forbidden`; the sign-in flow calls `/me` first. No membership is inferred. |
| Application user is inactive | 403 `forbidden`, including `/me`; never auto-reactivate. |
| Missing, blank, malformed, duplicated, or comma-joined business `X-Workspace-ID` | 422 `validation_error`, constant detail for `workspace_id`. |
| Selected workspace has no caller membership, whether nonexistent or inaccessible | 403 `forbidden`, identical body for both cases; do not reveal workspace existence. |
| Caller is a member but lacks the operation's role | 403 `forbidden`. |
| Record/reference absent from the authorized workspace, including another workspace's ID | 404 `not_found`, with the existing sanitized record/reference detail. |
| Malformed path/record UUID or invalid fields/JSON | 422 `validation_error`. |
| Admin requests an absent membership/target application user | 404 `not_found`; a non-admin never reaches target-user lookup. |
| Duplicate membership/slug, or removal/demotion of the last administrator | 409 `conflict`; constant field detail where applicable. |
| Database/JWKS dependency failure | 503 `service_unavailable`; unexpected failures remain 500 `internal_error`. |

Order protected handling as authentication, active application user, selector
syntax, workspace membership, operation role, then payload validation and scoped
record lookup. `/me` has the provisioning exception below. Invalid credentials
return 401 even if a body, query, or selector is invalid. The existing route
wrapper's prechecks and FastAPI's early JSON parsing mean a dependency alone is
insufficient for this ordering: authenticate at the protected route boundary
before invoking its normal parsing/validation handler. Reuse the verified
principal for that request; do not verify twice. Test combined-error cases.

For example, a workspace A member requesting a workspace B invoice while
selecting A gets 404. Selecting B without membership gets 403 before record
lookup. A valid but unmatched list filter still produces an empty scoped list;
it does not become a cross-workspace existence check.

Public foundation endpoints keep precisely their current behavior, without
requiring even an Authorization header:

- `GET /health`: 200 `{"status":"ok"}`, independent of all dependencies.
- `GET /ready`: 200 `{"status":"ready","database":"ok","redis":"ok"}`;
  on failure, 503 with `status: "not_ready"` and each dependency's actual
  `"ok"`/`"unavailable"` value. Recovery restores the healthy body.

Keep `/docs` and `/openapi.json` public schema-only resources and document bearer
security on protected operations only. They grant no business access. Health and
readiness retain their existing OpenAPI/body contracts.

## 5. Identity, workspace, and membership APIs

Paths below are backend paths; browser requests prepend `/api` for the existing
proxy. All endpoints in this section require the verified access token and use
the error contract above. No public user directory or email search is added.

### `GET /me`

After verification, find the exact `(issuer, subject)`. If absent, insert one
active `application_users` row, commit it, and return it without creating any
membership or workspace. Concurrent first requests use the unique constraint
and insert-on-conflict-do-nothing plus reread, so they return the same ID. Never
overwrite an existing user's status or identity. A failure rolls back and
returns a sanitized error; later retry can recover.

Return 200 with `user` containing `id`, `issuer`, `subject`, `created_at`, and
`updated_at`, and `memberships` containing the caller's current memberships only.
Each membership includes `id`, `workspace_id`, `application_user_id`, `role`,
`created_at`, `updated_at`, and a `workspace` object with `id`, `slug`, `name`,
and `created_at`. Sort memberships by workspace `created_at` then workspace ID
descending. This registration read deliberately persists only the caller's identity;
other endpoints require this initial registration. It grants no workspace access.

A newly signed-in user with no memberships sees their own application-user UUID
and `memberships: []`. They can copy that UUID to an administrator through an
existing trusted channel, refresh membership information after being added, or
create a new workspace. The app must not send invitations/messages itself.

### `GET /workspaces`

Return 200 with the existing pagination envelope `items`, `limit`, `offset`,
`total`. Defaults/ranges remain limit 20 (1-100), offset 0 (0-10000). Each item
contains workspace `id`, `slug`, `name`, `created_at`, plus the caller's `role`.
Join memberships by the current application-user ID; filter before counting,
sorting, or pagination. Sort by workspace creation time then ID descending.
No memberships means an empty list, never a list of all workspaces or demo access.

### `POST /workspaces`

Accept only `{"slug":"fictional-team","name":"Fictional team"}`. Trim both;
name is nonblank and at most 200 characters. Slug is at most 64 characters and
matches `^[a-z0-9]+(?:-[a-z0-9]+)*$`; reserve `local-demo` for the explicit seed.
Other fields, IDs, and requested owner/role are forbidden. A duplicate slug is
409; invalid/reserved input is 422. Existing workspace constraints still apply.

In one request transaction, create the workspace, flush its server UUID, lock
the caller's application-user row and recheck activity, insert the caller's
administrator membership, materialize the response, and commit once.
Return 201 only after that commit, with `workspace` (the four workspace fields)
and `membership` (the six membership fields listed above). This operation does
not require prior membership anywhere. A failed membership insert or commit
must leave neither row. No workspace-detail/edit/delete API is implied here.
Do not automatically retry a lost creation response; refresh the caller's
workspace list to locate the slug before a manual retry.

### Administrator-only membership APIs

Use the path workspace UUID as the sole selection and check the caller's
administrator membership there. All roles may see their own memberships through
`/me`; only administrators may inspect another member or the full member list.

| Endpoint | Request and success response |
| --- | --- |
| `GET /workspaces/{workspace_id}/memberships` | 200 paginated `items` of membership fields, limit/offset/count rules as above; order by membership `created_at`, then ID descending. |
| `POST /workspaces/{workspace_id}/memberships` | Only `application_user_id` (UUID) and `role` (exact role string); 201 saved membership. Target must already be an active application user; nonexistent/inactive target gives the same 404. Duplicate workspace/user pair gives 409. |
| `PATCH /workspaces/{workspace_id}/memberships/{application_user_id}` | Only `role`; 200 saved membership. A no-op is successful without changing `updated_at`. User/workspace ownership is immutable. |
| `DELETE /workspaces/{workspace_id}/memberships/{application_user_id}` | No body; 204 with no response body after commit. Absent membership is 404. |

The last path segment is the **application-user ID**, not the membership row ID.
The saved membership fields are `id`, `workspace_id`, `application_user_id`,
`role`, `created_at`, and `updated_at`. Unknown fields and invalid roles are 422.
There is no add-by-email, unverified subject input, invitation acceptance, or
public bootstrap endpoint. Knowing a user UUID grants no administrative power.
An administrator may change/remove their own membership only when the
last-administrator rule allows it. All mutations commit once or roll back fully.

## 6. Last administrator, concurrency, and local removal

Count administrators with an active application user; an inactive administrator
cannot preserve access for the workspace. An established workspace must retain
at least one such administrator. A simple count followed by an unlocked write
is unsafe: two administrators could each observe the other and both leave.

For every membership add/change/remove, use the same transaction protocol:

1. Lock the target `workspaces` row with PostgreSQL `SELECT ... FOR UPDATE`.
   This stable row serializes membership mutations even if a target membership
   does not yet exist. Use READ COMMITTED and a fresh query after acquiring it.
2. Reread caller activity and administrator membership after waiting for the
   lock, then resolve and lock the target application-user row and recheck its
   activity before an add/promotion. Use the workspace-then-user lock order for
   all mutation paths. Never rely on an earlier dependency result or cached
   SQLAlchemy relationship to authorize the mutation.
3. For administrator removal/demotion, count active administrators while
   holding the lock. If the proposed result is zero, return 409 without changing
   anything. Otherwise mutate and commit before releasing the lock.

New workspace creation establishes its first administrator in its own atomic
transaction. The demo grant below takes the same workspace lock. Use bounded
lock waiting; a lock timeout returns sanitized 503 and rolls back, with no
automatic mutation retry. Concurrency tests require two independent database
connections/transactions, not two savepoints on one connection.

Local user removal means setting `is_active=false` while retaining the identity
row as a tombstone. Hard deletion is not the removal mechanism: `/me` must never
recreate a removed user and restore access from an old JWT. No user-removal or
reactivation HTTP API is added by this milestone. Any later operator removal
tool must lock all affected workspace rows in sorted UUID order, recheck their
active administrators, and reject a change that strands a workspace. Serialize
target activity changes with membership additions by locking the target user row
after workspace locks; reread its membership set and retry if that set changed
before all locks were acquired. Do not introduce a raw status-update shortcut.

Each API request rereads application status and the selected membership from
PostgreSQL; do not cache authorization in a JWT, Redis, or a process-wide object.
A committed membership removal, role change, or user deactivation takes effect
on the next request with the **same still-valid JWT**. Requests already authorized
before that commit may finish; this does not promise cancellation of in-flight
work. Missing database access never falls back to cached permissions.

Logging out clears browser state and may revoke refresh capability, but **logout
alone does not immediately invalidate an issued JWT to an offline signature
verifier**. Revocation at Cognito or disabling a Cognito account is likewise not
a local database removal. Immediate application denial requires local
deactivation/membership removal; otherwise an existing access token can remain
usable until expiry (plus verifier leeway). Cognito explains this distinction in
[token revocation](https://docs.aws.amazon.com/cognito/latest/developerguide/token-revocation.html).

## 7. Explicit first demo membership and existing data

Plan a local operator-only command `python -m app.grant_demo_membership` with
required `--issuer` and `--subject`. It uses the existing database connection
configuration, never an AWS account key or a pasted bearer token. It is not
invoked by server startup, migrations, `seed_workspace`, or `seed_demo`.

The operator first has the intended person sign in and call `/me`. Using that
verified response, copy `user.issuer` and `user.subject` and independently check
the selected Cognito pool/issuer. Do not decode an unverified JWT or identify the
person by an email search. The command requires the issuer to exactly equal the
configured trusted Cognito issuer and the identity pair to already exist as an
active application user; a typo/unknown/disabled subject must fail. The CLI's
input is trusted only because a local operator deliberately supplies values
obtained through the verified sign-in, not because a copied string is a token.

Illustrative **Windows host PowerShell** invocation for later implementation
(Python runs inside the **Linux API container**; not executed in Step 4.1):

```powershell
docker compose exec -T api python -m app.grant_demo_membership --issuer 'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EXAMPLE' --subject 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
```

The example values are fictional, not a configured pool or account. The command
must find and lock the exact existing demo UUID/slug/name, refuse a missing or
conflicting workspace, and resolve the already registered user. If there are no
memberships, insert that user's administrator membership and commit. Repeating
for the same active administrator succeeds without changes. If memberships
already exist and this user is not already an administrator, fail rather than
add/promote another bootstrap user; the existing administrator uses the normal
API. A partial failure rolls back. Print only the application-user/workspace IDs
and outcome, never tokens, credentials, or private connection details.

This leaves existing records in place and grants their first deliberate reader.
Ordinary membership APIs handle further access. Neither seeds nor a fresh login
grant demo access. There is no email-based grant, startup grant, or public
bootstrap endpoint. The command's local database authority is an operator
capability; it must not be exposed through HTTP or browser controls.

## 8. Browser lifecycle, storage, and navigation

Use these exact registered local browser URLs:

- Callback: `http://localhost:5173/auth/callback`
- Logout return: `http://localhost:5173/`

There is **no hash fragment in the OAuth callback**. Start login on
`http://localhost:5173`, even though current README browsing uses `127.0.0.1`.
These are different storage origins. Canonicalize to `localhost` before creating
PKCE/state; copying state or tokens between hosts is forbidden. Verify later
that Vite's existing loopback binding serves the canonical hostname, including
local name resolution. Do not silently change the required callback to a numeric
host. Future deployed URLs require an explicit HTTPS allowlist and a server that
serves the SPA at `/auth/callback`.

Handle `window.location.pathname === "/auth/callback"` before ordinary hash
routing or business data loads. Let the library consume the query code/state
once, guard against repeated React effects/double exchanges, and remove the
callback query from browser history after processing. Then call `/me`, load
accessible workspaces, and navigate to a safe internal hash route. A saved return
route must be a validated local application route, never an external URL. Missing,
replayed, or mismatched state and failed code exchanges leave the app signed out
with an explicit retry. Do not echo provider descriptions or codes.

Configure library storage explicitly; its defaults do not meet this contract:

- `userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() })`
  keeps the User object, access token, ID token, and refresh token in memory.
- `stateStore: new WebStorageStateStore({ store: window.sessionStorage })`
  is permitted for short-lived PKCE/state/nonce correlation only. Use a dedicated
  prefix, clean consumed/cancelled/stale entries, and put no tokens or business
  drafts in it. Do not use `localStorage`, token cookies, or IndexedDB for tokens.
- Disable OIDC debug logging. No raw tokens enter URLs, logs, test snapshots, or
  application error messages. Cognito's own managed-login cookie is separate
  from application token storage.

The library documents [user/state storage settings](https://authts.github.io/oidc-client-ts/interfaces/UserManagerSettings.html)
and [InMemoryWebStorage](https://authts.github.io/oidc-client-ts/classes/InMemoryWebStorage.html).
Explicit memory storage means a browser reload or new tab may require a fresh
login redirect; a Cognito session may reduce interaction but the app cannot
recover its prior tokens. Unsaved drafts also disappear on full reload/redirect,
as they do now. This tradeoff is deliberate.

### Expiry, renewal failure, logout, and cancellation

Set `automaticSilentRenew: false`, `monitorSession: false`, and
`loadUserInfo: false`. Use a single coalesced renewal operation before expiry
(60 seconds early, and checked again
before dispatch after a suspended tab resumes). Call the library's refresh-token
renewal only while an in-memory refresh token exists; do not fall back to a
hidden iframe or an automatic redirect loop. Keep `validateSubOnSilentRenew`
enabled. Replace rotated refresh tokens in memory. Proposed Cognito lifetimes
are 15 minutes for access/ID tokens and eight hours for refresh tokens, configured
on the client later. Browser scheduling does not extend backend token expiry.
See the library's [Cognito settings](https://authts.github.io/oidc-client-ts/#provider-specific-settings)
and Cognito's [refresh-token contract](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-refresh-token.html).

Renewal has a bounded ten-second deadline. Missing refresh token, failed/expired
refresh, changed subject, or renewal timeout ends the local authenticated state:
stop timers, clear tokens and private records/drafts, cancel private requests,
and offer a new explicit sign-in. Do not keep using a token after renewal has
failed. A late renewal cannot restore a session after logout/cancellation.

An API 401 similarly ends the local session and offers login; do not replay the
failed operation. A 403 preserves login, refreshes `/me` and accessible workspace
information, and clears inaccessible records/controls. A 503 offers recovery,
not forced sign-out. Refreshing access information must not resend a write.

Logout immediately blocks new private requests, cancels in-flight work and
renewal, and clears the shared token store, private state, selected workspace,
and drafts. The logout operation may retain the refresh token in its own memory
only for a bounded best-effort library revocation attempt, then discard it
regardless of network outcome. The library's public
[`OidcClient.revokeToken`](https://authts.github.io/oidc-client-ts/classes/OidcClient.html#revokeToken)
accepts that token with type `refresh_token` after the shared store is cleared.
Set `revokeTokenTypes: ["refresh_token"]`; do not attempt access-token revocation.
Navigate the browser to the configured
Cognito domain's `/logout` with `client_id` and URL-encoded `logout_uri` equal to
`http://localhost:5173/`. Do not assume generic OIDC end-session discovery or
`post_logout_redirect_uri` parameters implement Cognito logout. Remain locally
signed out if provider logout fails. The provider behavior is documented at the
[Cognito logout endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html).

Cancelled/denied login or browser Back returns to a signed-out state without an
automatic retry. Invalidate the login attempt and remove its transient state;
an abandoned/replayed callback cannot sign the user in later. Clean stale state
on startup (15-minute maximum age). Use an authentication generation/completion
guard so old login, renewal, `/me`, and business promises cannot repopulate state.
Replace the manager's private in-memory user store when invalidating a session;
a late library completion must remain confined to its discarded store.

Keep Status available signed out. After `/me`, show the caller's own ID and a
workspace selector populated only by accessible workspaces. With zero, show
create-workspace and copy-own-ID options. With one, it may be selected; with
several, require a choice. There is no demo default. Show read navigation to all
members, create controls to administrators/accountants, and member management
only to administrators.

Business requests carry the current access token and selected `X-Workspace-ID`
only to the configured same-origin `/api` path. Include user/workspace/session
generation in request and cache keys, cancel obsolete reads on workspace change,
and clear private views, pickers, drafts, and feedback before loading another
workspace or identity. Preserve five-second request bounds and completion guards.
Aborting an already dispatched write does not prove rollback: retain a warning
associated with its original workspace and check that workspace's list before
retrying. Never replay POST/PATCH/DELETE automatically after auth, timeout,
cancellation, navigation, or a workspace change. No record may be resubmitted
under a newly selected workspace by a late continuation.

## 9. Required configuration and startup validation

These are proposed setting names, not values read from any local environment
file. All browser `VITE_` settings are public build-time configuration. No secret
belongs in them. Do not add actual environment files in Step 4.1.

| Public frontend setting | Meaning and validation |
| --- | --- |
| `VITE_COGNITO_ISSUER` | Exact HTTPS Cognito user-pool issuer, also the OIDC authority; no query/fragment, credentials, or trailing slash. |
| `VITE_COGNITO_CLIENT_ID` | Nonblank public browser app client ID; matches backend and the configured pool/client. No client secret. |
| `VITE_COGNITO_DOMAIN` | Controlled HTTPS managed-login origin, distinct from the issuer; used for Cognito logout. No path/query/fragment/credentials. |
| `VITE_AUTH_REDIRECT_URI` | Exact local callback above; deployed builds require a separately approved HTTPS callback on the application origin. |
| `VITE_AUTH_LOGOUT_URI` | Exact local logout return above; deployed builds require a separately approved HTTPS return on the same application origin. |

Keep the same-origin `/api` prefix rather than adding an arbitrary token-bearing
API URL setting. Code constants define code/query/PKCE, scope, storage, and
renewal policy. Validate all public settings before initializing authentication;
missing/malformed/inconsistent values show a clear configuration failure, keep
private routes disabled, and leave public Status usable. There is no unsigned
demo fallback. Confirm discovery issuer matches configured authority and check
token/logout endpoints against the controlled Cognito domain before use.

| Backend setting | Meaning and validation |
| --- | --- |
| `COGNITO_ISSUER` | Required exact trusted HTTPS Cognito user-pool issuer, validated against supported Cognito issuer host/pool syntax; one pool per deployment. Never derived from a request. |
| `COGNITO_CLIENT_ID` | Required nonblank public browser client ID; used for the access-token `client_id` equality check. |
| Existing `POSTGRES_*`, `REDIS_HOST`, `REDIS_PORT` | Retain database/session and readiness configuration; do not expose values in logs. No additional database or Redis auth-session store is proposed. |

Derive JWKS URL; do not expose an arbitrary production `JWKS_URL` or key-file
override. Fix RS256, 30-second leeway, cache/deadline bounds, and role rules in
code. Fail API startup clearly for missing/malformed identity configuration;
do not start with unprotected business routes. Validate configuration without
logging raw values. Migrations and seed CLIs remain separate from web startup
and require no Cognito network call. The grant CLI additionally needs the trusted
issuer configuration. Live backend verification uses public signing keys, not
AWS IAM credentials or a browser client secret.

There is **no production authentication bypass**: no auth-disabled flag, magic
header, fixed user, accept-unsigned mode, test token, email allowlist, local host
exception, or demo-user fallback in the production entrypoint. Unknown settings
must not select a test verifier. A configured production verifier always verifies
signatures and resolves database permissions.

## 10. Isolated verification and disposable HTTP checks

This is the later test plan; none of these runtime checks ran in Step 4.1.

| Test area | Required evidence |
| --- | --- |
| Cryptographic verifier | Generate ephemeral RSA keys with `cryptography`; sign real RS256 JWTs and expose only their public JWKS to the real verifier. Check valid access, tampered payload/signature, wrong key/issuer/client/type/algorithm, ID token rejection, missing/malformed claims/headers, `aud` rejection, expiry/iat/nbf/leeway, unknown/rotated `kid`, bounded refresh/cache, outage and recovery. Never mock verification success or disable signature checks in permission/API tests. |
| Identity registration | Concurrent first `/me` calls return one application-user ID and zero memberships; same email cannot merge identities; distinct issuer/subject pairs stay distinct; inactive tombstone cannot be recreated/reactivated. Failure before commit rolls back and later requests recover. |
| Workspace creation/discovery | New user with zero memberships can create; creator is sole administrator; inaccessible workspaces and their counts never appear. Enforce slug/input constraints and duplicate concurrency. Inject a late membership/commit failure and prove neither workspace nor membership persists. |
| Permission matrix | Every role reads all four resource types; only administrators/accountants create; only administrators list/add/change/remove members. Check anonymous 401, non-member/insufficient-role 403, cross-workspace scoped 404, malformed/missing selector 422, ignored forged identity/role headers, path/header rules, and combined-error ordering. |
| Membership invariants | Existing-user-ID add only; duplicate, unknown/inactive target, invalid role, self-change/removal, no-op, and last-admin 409. On independent PostgreSQL connections, race two self-removals/demotions and a removal against demotion; one effective administrator remains. Recheck caller authorization after a competing change and prove rollback/lock-timeout recovery. |
| Immediate local changes | Reuse the same signed unexpired token after membership deletion, role change, and local user deactivation; the next API request sees each committed change. Check no authorization-cache fallback on database outage. |
| Schema and existing records | Fresh upgrade and upgrade from populated `0001_manual_records`; named checks/FKs/indexes match ORM. Preserve all existing workspace/business IDs, timestamps, exact decimal strings, links, counts, and seed repeatability. Keep schema-only downgrade/upgrade on an empty guarded disposable database. |
| Frontend helpers and browser | Test explicit memory userStore/sessionStorage-only transient state, no token in browser persistence, PKCE/query callback once, state mismatch/replay/cancel, reload, expiry/refresh failure, rotated refresh, logout failure, stale completion, 401/403/503, workspace switching, role controls, and no mutation replay. Retain all status, decimal, form, selection, cancellation, and uncertain-write tests. Use synthetic callback/token responses without AWS for automation; record a later real Cognito browser check separately. |
| Public endpoints/OpenAPI | Preserve health/readiness bodies, dependency independence, outages/recovery and existing status tests without credentials. Document bearer security and actual 401/403 envelopes/headers on protected operations, and 204 membership deletion. |

Retain approved disposable project names, the actual PostgreSQL 17 database/user
and per-project marker check, explicit `RUN_POSTGRES_TESTS=1`, no development
fallback, and existing outer-transaction/savepoint cleanup. Current fixtures
import the module-level app; plan an application factory so each test app can
receive immutable synthetic verifier settings and a controlled JWKS transport
without importing a misconfigured production singleton. Inject **key sources and
settings**, not an authenticated identity or successful decode result. Keep
ordinary non-PostgreSQL tests runnable offline with their explicit integration
skips. Concurrency tests use guarded committed fixtures on separate connections
with their own targeted cleanup.

### Preserve the live HTTP checker's value

TestClient dependency overrides do not affect the running Uvicorn process.
Plan `backend/tests/run_http_api.py` as a separate disposable-only entrypoint,
launched by `compose.ci.yaml` in place of the production command. It constructs
the same application factory and real PyJWT verifier with an injected fictional
Cognito-shaped issuer/client and controlled local JWKS transport. Use the same
fictional issuer in the grant CLI's configuration; its normal issuer validation
still applies. The production entrypoint
cannot activate this harness through settings. The harness first validates the
existing disposable target settings; database-marker checks remain mandatory
before migrations, tests, seeding, or fixture membership writes. Health can still
run before migrations. No harness starts in the ordinary development stack.

Generate ephemeral signing keys before that HTTP server starts. Keep the private
key only in a disposable checker-owned file with restricted access; the API
verifier receives only a public JWKS file through the injected key source. The
checker signs a new short-lived test access token per phase, including after
container restart. Retain keys across that restart, then clean them with the
disposable project. Do not put keys/tokens in Git, logs, record snapshots, or
workflow artifacts. The API process must use real signature/claim checks and
real database memberships; a loopback request alone never grants identity.

After migrations and pytest (whose schema lifecycle tests require an empty
database), run the current explicit workspace/demo seeds. Register the signed
synthetic caller through `/me`, then explicitly grant its demo administrator
membership using the operator CLI under the disposable guard. Extend
`check_demo.py` to send bearer and `X-Workspace-ID` on every business request,
and to verify unauthenticated 401, valid non-member 403, and scoped record 404.
Capture twice-seeded detail/list/filter snapshots as today. Restart only API
and PostgreSQL with volume and key artifacts retained, sign fresh tokens, and
verify the identical records and persisted memberships through actual HTTP.
Never replace these reads with direct database assertions or skip them because
authentication was added.

Keep `check_endpoints.py` exercising public health/readiness **without** tokens
before migrations and through the existing PostgreSQL/Redis outage and recovery.
Retain full-body deadlines, fail-fast guards, sanitized failure logs, cleanup
even on failure, and read-only CI permissions. Extend local PowerShell checker
and CI in the same way. Tests use generated keys, synthetic users, and local
services only: **no live AWS credentials, accounts, endpoints, or calls in CI**.
Test key transports must fail if they attempt a real network fetch, including
when an untrusted token supplies a different issuer or key URL.
Do not obtain Cognito tokens or provision a real pool in a workflow job.

## 11. Planned files and rollout order

The paths below describe later work only; Step 4.1 creates none of them.

| Planned new file(s) | Purpose |
| --- | --- |
| `backend/app/auth/settings.py`, `jwt.py`, `__init__.py` | Validated production settings, immutable verified principal, RS256 verification and bounded trusted JWKS source. |
| `backend/app/models/application_user.py`, `workspace_membership.py` | Two new identity/access tables. |
| `backend/migrations/versions/0002_auth_workspaces.py` | Additive schema-only revision after the applied initial migration. |
| `backend/app/services/identity.py`, `workspaces.py`, `memberships.py` | Caller registration, atomic workspace creation, membership queries, and locked role mutations. |
| `backend/app/schemas/identity.py`, `workspace.py`, `membership.py` | Strict request/response contracts and role literals. |
| `backend/app/api/me.py`, `workspaces.py`, `memberships.py` | Protected identity/workspace and administrator-only membership endpoints. |
| `backend/app/grant_demo_membership.py` | Explicit local first-demo-administrator grant. |
| `backend/tests/auth_helpers.py`, `test_auth.py`, `test_identity.py`, `test_authorization.py`, `test_memberships.py`, `test_grant_demo_membership.py`, `run_http_api.py` | Generated keys, signature/permission/atomicity/concurrency/operator checks, and separate HTTP-server harness. |
| `backend/scripts/check_auth.py` | Guarded disposable key preparation, signed HTTP test credentials, and access-negative checks shared with the demo checker. |
| `frontend/src/auth.ts`, `authContext.tsx`, `authTypes.ts` | Library configuration, callback/renewal/logout lifecycle, session-generation guards, and typed caller/workspace state. |
| `frontend/src/components/WorkspaceSelector.tsx`, `pages/AccountPage.tsx`, `pages/WorkspaceNewPage.tsx`, `pages/MembershipsPage.tsx` | Own-ID display, workspace choice/creation, and administrator member management. |
| `frontend/tests/auth.test.mjs`, `workspaces.test.mjs` | Auth/storage/lifecycle/request-scope and workspace/role UI helper checks using the existing Node runner. |

Later modifications are expected in backend `main.py` (factory and production
entrypoint), model imports, dependencies, all four business routers, error
schemas/wrapper, fixture/schema/OpenAPI/business/seed/checker tests, and
`check_demo.py`/HTTP request helper. Seeds keep their current no-grants semantics.
Declare and lock PyJWT with cryptography in backend manifest/lockfile, and
`oidc-client-ts` in frontend manifest/lockfile without unrelated upgrades.
Frontend App/navigation/API/types/hooks need auth/workspace integration; retain
the independent status module. Update README/demo setup instructions and public
setting documentation later. Compose development configuration must pass the
required backend settings; only the CI override selects the disposable harness
and its key artifact handling. Update both check orchestration paths and image
packaging if needed. These are future integration changes, not this checkpoint's
permission to edit infrastructure or local environment files.

Implement and roll out in this dependency order without calling later features
complete early:

1. Review this contract and keep Step 4.1 documentation checks separate from
   implementation results. No approval/extraction work joins Milestone 4.
2. Add locked auth dependencies, settings/verifier, application factory, and
   generated-key tests; add the two models and `0002_auth_workspaces`. Prove
   fresh and populated disposable upgrades before any local database upgrade.
3. Implement `/me`, workspace APIs, locked membership services/APIs, role and
   workspace dependencies, protected business routers, errors, and grant CLI.
   Update authenticated fixtures and the disposable HTTP harness/checkers as
   part of the same verified backend change; do not leave a public demo fallback.
4. Add browser PKCE callback, memory storage/lifecycle, own ID, selection,
   workspace/member pages, role controls, and authenticated request handling.
   Run frontend tests, lint, build, and synthetic browser checks. Adapt the local
   setup instructions to the canonical origin before asking anyone to sign in.
5. Run the complete disposable backend checker and frontend checks. Confirm the
   live authenticated seed/persistence proof and public outage/recovery checks
   both pass, and no test calls AWS. Record exact local results. Later CI results
   must be tied to the actual separately authorized submitted revision.
6. For a later deliberately chosen local synthetic demonstration, have the
   operator configure a Cognito user pool/public client/domain and register the
   exact URLs, code grant, PKCE, scopes, and token lifetimes. Validate the matching
   public frontend/backend settings without printing secrets. This document does
   not authorize cloud provisioning or access to local settings files.
7. Before serving upgraded business routes, stop the old unauthenticated API and
   keep the existing PostgreSQL volume. Explicitly apply `alembic upgrade head`
   in the Linux API container to add `0002_auth_workspaces`; never use
   `down --volumes` or rewrite the initial revision. Existing records stay put.
8. Start the configured protected API/frontend, sign in on `localhost`, call
   `/me`, and use the explicit local operator command for the first demo grant.
   Refresh workspace discovery and verify all roles and unchanged demo records.
   An operator may run existing seeds explicitly only when desired; no seed or
   membership grant runs automatically.
9. If rollout fails, leave business access closed, correct configuration/code,
   and retry without deleting data. Do not restore an unauthenticated API over
   the upgraded database or downgrade away memberships as routine recovery.

Step 4.1 ends with this contract and the progress update. Runtime authentication,
the migration, dependencies, settings, operator command, browser login, and all
test/checker changes above remain unimplemented until later requested work.
