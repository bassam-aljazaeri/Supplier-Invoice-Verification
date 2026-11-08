# Supplier-Invoice-Verification: private document processing contract

Step 5.1, 2026-10-28: proposed contract prepared; user review pending.
This checkpoint changes documentation only. Everything described as new below
is planned for Steps 5.2-5.7, not implemented or verified at runtime here.

## 1. Scope and relationship to invoices

Accept one fictional invoice file per request: PDF, JPEG, or PNG, with
**1-5,000,000 bytes inclusive** (decimal 5 MB). A PDF must be unencrypted and
contain exactly one page; reject encrypted PDFs even if an empty password could
open them. An image must decode successfully, have exactly one frame, positive
dimensions, at most **10,000,000 decoded pixels** (`width * height`), and neither
dimension above 10,000 pixels. Reject APNG, animated PNG, and multi-image JPEG
containers. These are conservative first-release limits, not browser hints.

An upload creates a workspace-owned **document**, separate from `invoices`.
It never creates an invoice with empty, guessed, or invented supplier, number,
date, line, tax, or monetary values. Existing manual drafts, suppliers, orders,
delivery records, seeds, decimal rules, and all their workflows stay unchanged.
`accepted` means only that the file passed this structural validation contract;
it does not establish invoice accuracy, uniqueness, approval, or safety.

Step 5 excludes ZIP files, multiple files, bulk uploads, OCR, Textract,
embeddings, extraction, matching, approvals, and exports. In later Step 6, an
accepted document may be selected for extraction with source evidence, then
human correction/review before explicitly creating or linking business records.
That requires a separate contract. Do not add invoice links, extraction tables,
extracted fields, or guessed business defaults in Step 5.

## 2. Inspected baseline and process responsibilities

The current repository has ten application tables, migration head
`0002_auth_workspaces`, scoped manual-record services, and synchronous SQLAlchemy
transactions. `api/authorization.py` authenticates before body validation and
resolves current database membership. `BusinessRoute` provides sanitized errors
and `no-store`. Browser requests use `/api`, memory tokens, generation guards,
cancellation, five-second deadlines, and no automatic write replay. Compose has
API, PostgreSQL 17, and Redis 7; there is no document storage or worker yet.
The guarded PowerShell checker/CI use a separate signed HTTP harness, isolated
database/project markers, migrations, repeated seeds, persistence snapshots,
and public dependency outage/recovery checks. Preserve those checks.

| Process or dependency | Purpose in Step 5 |
| --- | --- |
| FastAPI API | Verify Cognito access token and workspace permission; bound multipart input; reserve/finalize uploads; expose scoped metadata, explicit retry, and authorized download grants. Never perform expensive parsing in a request. |
| PostgreSQL | Authoritative document results, upload ownership, idempotency, and durable job/dispatch scheduling. A committed job survives lost broker messages. |
| Existing Redis | Celery broker on a dedicated queue/key prefix, not the authoritative status store. No file bytes, bearer tokens, credentials, or signed URLs in messages. |
| Celery worker | Separate Linux Docker service, same backend image, prefork pool/concurrency 1 initially. Claim a database job, retrieve bounded bytes, run isolated structural validation, and conditionally save the outcome. |
| Dispatcher/reconciler | One small long-running Python process in another service using the backend image. Poll PostgreSQL every five seconds in batches of 20; publish due jobs, recover dispatch/processing/upload leases, and perform bounded cleanup. No Celery Beat is needed. |
| Storage adapter | Private immutable bytes. Boto3/S3 is the cloud target; a private shared Docker named volume is the smallest local option. |

No MinIO, LocalStack, RabbitMQ, Kafka, Kubernetes, Celery result backend, or
monitoring service is required. The dispatcher is a process with database
coordination, not a second broker. API/worker/dispatcher startup does not run
migrations, seed data, or create AWS resources. Python 3.12 and parser resource
limits run inside Linux containers; Windows host commands remain PowerShell.

### Narrow storage boundary and local development

Define `put_new(key, file, size, sha256)`, `open_bounded(key, max_bytes)`,
`stat(key)`, `delete(key)`, and `download_grant(document, expires_in)`.
Add a paginated, server-prefix-only orphan scan for reconciliation. Return typed
missing/transient/integrity failures, never raw SDK exceptions. Tests substitute
controlled adapters, not AWS. Bucket, root directory, and adapter selection are
trusted process configuration; request fields cannot override them.
Local mode is the explicit development/test default; S3 requires explicit
configuration and must never silently fall back to local storage after an error.

For local development, mount one private named volume into API/worker/dispatcher
outside all static/web roots. Use fixed-root containment, no symlink traversal,
exclusive immutable creation, and atomic completion of local writes. Give only
these containers access. Temporary partial files have separate generated names
and are never readable as completed objects. No extra storage service is needed.
This exercises upload, worker reads, restart recovery, cleanup, and downloads
without AWS charges. It does **not** verify S3 policies, IAM, encryption,
presigning, network failures, or durability across hosts. Docker-volume privacy
does not imply encryption at rest or production-grade storage.

The S3 adapter uses a general-purpose private bucket and single-object
`put_object`, with conditional creation (`IfNoneMatch="*"`), explicit SHA-256
checksum, and bounded SDK attempts/deadlines. Do not use multipart S3 transfers
for these small files. A preexisting key is successful only after verifying its
size and SHA-256; S3 ETags are not the application's SHA-256. See the
[Boto3 put_object contract](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html).

## 3. Minimum additive schema

Add only `documents` and `document_jobs` in a new revision
`0003_documents`, after `0002_auth_workspaces`. Do not edit applied migrations.
Use existing named constraints, server UUIDs, and UTC `TIMESTAMPTZ` conventions;
all counters/sizes are integers. The tables contain no invoice business values.

| `documents` fields | Proposed types and rules |
| --- | --- |
| `id`, `workspace_id`, `uploader_id` | Server UUID PK; required workspace FK and application-user FK, both `ON DELETE RESTRICT`. Uploader is the verified application user, not request input. Membership removal retains this provenance. |
| `upload_attempt_key` | Required canonical UUID from `Idempotency-Key`; unique `(workspace_id, uploader_id, upload_attempt_key)`. The operation scope is implicitly `POST /documents`, the only operation using this field. Retain it for the record's lifetime. |
| `storage_key` | Required, unique, server-generated opaque key, at most 512 characters, e.g. a fixed application prefix plus workspace/document/random UUIDs. Never a filename or client path; immutable after reservation. |
| `original_filename` | Required display basename, 1-255 characters after removing path components; reject control characters and invalid/blank names. Retain Unicode as display text, escape on rendering. Never use it as a path or log field. |
| `byte_size`, `sha256` | Required integer 1-5,000,000 and lowercase 64-character hexadecimal digest, computed incrementally by API. Required before reservation; immutable. No unique digest constraint. |
| `detected_type` | Nullable enum `pdf`, `jpeg`, `png`; authoritative only after worker validation. No trusted browser MIME column is needed. |
| `state`, `error_code` | Required state below, default `receiving`; nullable allowlisted safe error code, no raw parser/SDK message. |
| `upload_token`, `upload_lease_until` | Nullable UUID owner token and timestamp, present together only during `receiving`. Initial lease is 120 seconds after reservation; ownership fences finalization and reconciliation. |
| `created_at`, `updated_at`, `uploaded_at`, `finished_at` | First two required with server defaults; uploaded time nullable until private bytes are finalized; finished time present only for terminal outcomes. Update timestamps explicitly on transitions. |

| `document_jobs` fields | Proposed types and rules |
| --- | --- |
| `document_id`, `workspace_id` | `document_id` is PK (one job per document). Composite FK `(workspace_id, document_id)` to `documents(workspace_id, id)`, `ON DELETE RESTRICT`; ownership cannot diverge. No separate job UUID is necessary. |
| `dispatch_state` | `pending`, `publishing`, `published`, or `inactive`. `inactive` means running or terminal; document state distinguishes those. This is transport scheduling, not a duplicate processing result. |
| `next_dispatch_at`, `dispatch_token`, `dispatch_lease_until`, `last_published_at` | Nullable timestamps/UUID; due time for publishing, temporary publication owner/30-second lease, and last successful publication. Token/lease exist together only while `publishing`. |
| `attempt_count`, `manual_retry_count` | Required integers default 0; lifetime processing claims 0-6 and explicit retry cycles 0-1. Dispatch/redelivery alone does not increment processing attempts. |
| `attempt_token`, `processing_lease_until` | Nullable UUID and timestamp present together only for a claimed attempt. Fresh unpredictable token per claim; 120-second nonrenewable lease. Never reuse a Celery task ID as ownership. |
| `next_attempt_at`, `created_at`, `updated_at` | Next eligible processing time, nullable when running/terminal; required creation/update timestamps. Database time controls eligibility and leases. |

Require unique `documents(workspace_id, id)`, list index
`(workspace_id, created_at, id)`, uploader FK index, and a partial receiving
index on `upload_lease_until`. Job indexes cover due dispatch
`(next_dispatch_at, document_id)` for pending/published rows, publishing-lease
expiry, and processing-lease expiry. The idempotency unique index also supports
caller-scoped recovery queries. Name enum/range/digest/text/null-pair checks and
foreign keys in both models and migration. No index/deduplication across
workspaces by file hash. State-dependent checks require a detected type for
`accepted`, no error for accepted/nonterminal states, and a safe code for
`rejected`/`failed`. Services update paired document/job state in one transaction;
cross-table invariants also need real PostgreSQL tests.
Use document-operation lock/statement timeouts of three/five seconds respectively;
lease comparisons use the current database clock after acquiring locks. Do not
change transaction settings for existing manual-record operations.

The document is the sole public result; its job is the durable outbox and
scheduler. Do not add separate outbox, task-result, upload-session, extraction,
or attempt-history tables for this milestone. Upload ownership and the one
current processing attempt are sufficient; structured safe logs provide limited
operational history, not a financial audit trail.

## 4. States and safe outcomes

| Document state | Meaning | Allowed next states |
| --- | --- | --- |
| `receiving` | A bounded file has been hashed and reserved; private storage/finalization may be incomplete. No job can run yet. | `queued`, `failed` |
| `queued` | Private bytes and the durable job were committed together; may be waiting for dispatch, broker recovery, or `next_attempt_at`. | `processing` |
| `processing` | One unexpired database-owned validation attempt. | `accepted`, `rejected`, `queued`, `failed` |
| `accepted` | Supported file structurally validated. Terminal in Step 5. | None |
| `rejected` | Deterministic invalid/unsupported document. Terminal; no retry of these bytes. | None |
| `failed` | Upload could not finish, integrity failed, or processing exhausted its current retry budget. Terminal unless eligible for one explicit processing retry cycle. | `queued` only under retry rules below |

`processing -> queued` is only a temporary failure/expired-lease recovery;
it sets the next eligible time. A failed upload never goes directly to accepted.
All other transitions are forbidden. No user endpoint marks a document accepted.

Worker rejection codes: `invalid_file`, `unsupported_type`, `pdf_encrypted`,
`pdf_page_count`, `image_frame_count`, `image_dimensions`, `parser_limit`.
The last means the document exceeds the supported parser time/memory budget,
not a transient network outage. Failed-processing codes: `storage_unavailable`,
`processing_interrupted`, `processing_error`; these permit the bounded explicit
retry cycle. `upload_incomplete` and `storage_integrity` are nonretryable failures;
offer a fresh upload with a new key. A temporarily missing stored object counts
as storage failure and follows the processing retry budget. Unknown exceptions
map to `processing_error`; diagnostics must not expose inputs or exceptions.
HTTP request errors and persisted document error codes are separate contracts.

## 5. Upload consistency and idempotency

There is no shared PostgreSQL/S3 transaction. Use this sequence:

1. Authenticate, resolve active user, validate exactly one canonical
   `X-Workspace-ID`, check current membership/upload role, then validate the
   idempotency header and multipart headers. Perform these checks before reading
   or spooling the body. Preserve existing 401/403 precedence and sanitized errors.
2. A document-specific streaming multipart adapter (using `python-multipart`)
   counts **all received body bytes**, capped at **5,065,536 bytes**, including
   boundaries/headers. `Content-Length` can reject early but cannot be trusted
   as the only limit; enforce absent, chunked, and understated-length cases too.
   Accept only `multipart/form-data`, no request content encoding, exactly one
   file part named `file`, no text fields or additional parts. Bound boundary
   length to 70 characters, each part's headers to 8,192 bytes/16 headers, and
   aggregate multipart overhead to 65,536 bytes. Stop on a second part.
3. Count file chunks separately and stop at byte 5,000,001. Hash while streaming
   to one private temporary file (64 KiB chunks; never buffer the whole body).
   Reject empty files, invalid names, and signatures outside PDF/JPEG/PNG before
   reserving a row. Recognized signatures are only candidates, not validation.
   Cap receive time at 60 seconds, idle reads at ten seconds, and four concurrent
   uploads per API process; excess concurrency returns safe 503. A dedicated
   32 MiB temporary mount bounds disk use. Close/remove files in `finally`,
   including malformed multipart, timeout, disconnection, and cancellation.
4. Reserve `receiving` in a short database transaction with the unique scoped
   key, content fingerprint `(sha256, byte_size, original_filename)`, generated
   storage key, upload owner token, and lease. Commit before writing storage.
   Do not hold a database lock during network/storage I/O. If this commit is
   uncertain, confirm the reservation/owner before attempting a storage write.
5. Write immutable private bytes with a 15-second total storage-operation bound.
   In a new transaction, finalize only if state, token, and unexpired upload
   lease still match: set `queued`/`uploaded_at`, clear upload ownership, and
   insert the pending job with both due times now. Commit those changes together.
   For a new upload, respond 202 only after this durable queued commit; receiving
   replays are the explicit exception below. Broker availability is not
   needed for this response. The overall API/browser upload deadline is 90
   seconds; ordinary reads and manual-record request deadlines stay five seconds.

The implementation must enforce limits **before/during multipart parsing**;
reading an unrestricted `UploadFile` and checking its length afterward is
insufficient. Framework spool thresholds and form-field limits are not file-size
limits. Implement/test the bounded adapter against the locked framework version,
without assuming a newer framework's body-limit API exists. See
[Starlette request/form behavior](https://starlette.dev/requests/).

### Replays, failures, and cleanup

- A stable high-entropy `Idempotency-Key` belongs to one workspace, caller, and
  create-document operation. Parse/hash a replay within the same bounds before
  comparing its fingerprint. Same scoped key and different bytes, size, or
  display filename returns 409 without replacing anything. Identical bytes
  under a new key are a distinct document; they are not proof of a duplicate
  business invoice. No cross-workspace deduplication or existence signal.
- Concurrent reservations serialize through the unique constraint (bounded lock
  wait, then safe 503). The loser rereads after conflict/rollback. Same fingerprint
  returns the existing document: 202 if receiving/queued/processing, 200 if
  terminal. Only the owner writes storage. A replay never starts another upload
  or processing attempt, resets retries, or extends an active lease. Authorization
  is checked again even for a previously successful key.
- Storage failure after reservation leaves a recoverable receiving record and
  returns safe 503. Storage success followed by failed/uncertain final database
  commit leaves bytes private; do not blindly delete them, since the commit may
  have succeeded. Reread when possible, otherwise let reconciliation decide.
  No pending job may reference a merely reserved/incomplete upload.
- On an expired receiving lease, the reconciler atomically takes a new upload
  token/120-second lease, invalidating the old owner. With bounded storage reads,
  verify the reserved key's size and SHA-256. Matching complete bytes can finalize
  queued plus the job under the new token; confirmed absence becomes failed
  `upload_incomplete`, mismatch failed `storage_integrity`. On storage outage,
  defer checks; after 15 minutes from reservation, close as `upload_incomplete`.
  Clear ownership on closure. Late API finalization must fail its ownership check.
- Sweep temporary files older than ten minutes only when no active request/parser
  owns them; container restart removes ephemeral temp mounts. Each reconciliation
  pass performs at most 100 cleanup candidates. Scan only the configured owned
  storage prefix, paginate, and ignore objects younger than 24 hours. Delete only
  keys unreferenced by any document or belonging to closed `upload_incomplete`
  reservations, after a fresh database/ownership check. Never infer an orphan
  from a database outage, listing failure, or age alone. Late writes from fenced
  owners are caught by subsequent scans. Retain accepted/rejected and other failed
  document bytes privately; general retention/deletion is a later policy.
- Status/list reads recover uncertain browser outcomes. Never automatically
  resend a browser write after timeout, token renewal, navigation, cancellation,
  sign-in, or workspace change. An abort is not proof of server rollback.

## 6. Durable dispatch, claims, and recovery

The job row is a minimal transactional outbox: the API records both queued
document and pending work in one PostgreSQL transaction. A process can die after
that commit but before publishing to Redis. Publishing inside the API transaction
would instead risk a task running before commit or surviving rollback; it would
not provide a shared transaction. The dispatcher closes these gaps as follows:

1. Select due pending jobs using `FOR UPDATE SKIP LOCKED`; check queued document
   and `next_attempt_at <= database now`. Set publishing token/30-second lease,
   commit, then publish outside the transaction with a ten-second publish bound.
   Message arguments are only `{"document_id":"50000000-0000-4000-8000-000000000001"}`.
   Celery envelopes may contain their own task IDs; neither ID grants authority.
2. Conditional publication success sets `published`, `last_published_at`, and
   `next_dispatch_at = now + 180 seconds`. Failure returns pending with dispatch
   due in 30 seconds. If publication succeeded but bookkeeping failed, the
   30-second publishing lease expires and publication is repeated. If the worker
   already claimed it, the publisher's token update loses harmlessly.
3. A published queued job not claimed within 180 seconds becomes pending again.
   Recover expired publishing leases too. This recovers Redis restart, broker
   outage, lost messages, and API/dispatcher interruption. Broker-only retries
   have bounded per-call work and fixed scheduled delays, and do not exhaust
   processing attempts; queued work waits for infrastructure recovery.
4. On delivery, load document/job from trusted database IDs and their composite
   ownership relation. In a short transaction lock document then job; require
   queued, due, remaining budget, and no active processing owner. Atomically
   increment attempt count, set processing/fresh attempt token/120-second lease,
   set dispatch inactive, and clear dispatch ownership/due times and
   `next_attempt_at`. Commit before
   storage reads/parsing. Another delivery sees processing or a terminal state
   and performs no work. A task-supplied workspace is never authorization.
5. Read at most the recorded size/5,000,000 bytes from the reserved private key,
   verify SHA-256, validate in the bounded parser subprocess, then commit document
   outcome plus job changes together. Completion requires processing state,
   matching attempt token, and `processing_lease_until > database now`. A stale
   or expired attempt cannot complete, renew itself, schedule a retry, or clear a
   newer owner's fields. It discards results and its own temporary files only.
6. Temporary attempt failure, or reconciliation of an expired processing lease,
   conditionally clears that owner and queues another attempt: ten seconds after
   claim 1, thirty seconds after claim 2; after claim 3 mark failed. One explicit
   retry cycle permits lifetime claims 4-6 with the same delays after claims 4/5.
   Claim 6 exhausts all retries. Lease recovery does not increment again; the
   abandoned claim already counted. Permanent invalid files go directly to
   rejected and never retry. Terminal jobs are inactive with all due/lease/owner
   fields cleared. No locks remain held while parsing or accessing storage.

Use database scheduling, not Celery `retry()`, autoretry, ETA, or countdown, to
avoid competing retry counters and schedules. Tasks can be delivered more than
once, and Redis messages can also be lost; reconciliation restores eligible work.
This design does not promise exactly-once execution. Structural validation is
read-only/idempotent, and database ownership makes only the current outcome win.

### Celery acknowledgement and resource coordination

Proposed Celery settings: JSON-only messages, `task_ignore_result=True`, no result
backend, `task_acks_late=True`, `task_acks_on_failure_or_timeout=True`, and
`task_reject_on_worker_lost=False`. Acknowledge after a durable outcome/requeue
commit, or after a verified duplicate/no-op. If the database cannot record an
outcome, let the task fail; acknowledgement may still occur, so database leases
and reconciliation remain necessary. Avoid immediate worker-loss requeue loops.
These are explicit choices based on [Celery task acknowledgements](https://docs.celeryq.dev/en/stable/userguide/tasks.html).

Use prefetch multiplier 1, concurrency 1, soft task limit 45 seconds, hard limit
60 seconds, and a 512 MiB worker container limit. Set Redis broker visibility
timeout to 180 seconds consistently across document publishers/workers; set the
app visibility timeout consistently where required by the pinned release, with
no result backend to configure. Enable cancellation of late-ack tasks on broker
connection loss. These settings must be verified with the chosen Celery/Kombu
lock; they are proposed application limits, not guarantees from defaults. See
[Celery configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html).

The 60-second task cap fits inside the 120-second processing lease and 180-second
visibility timeout. An early duplicate cannot steal an unexpired lease; an old
delivery after recovery is fenced by database state/ownership. Broker visibility
restoration is not an exact timer, and orderly shutdown may redeliver sooner.
The reconciler can therefore schedule replacement work independently, and any
overlap is safe. Keep delayed retries in PostgreSQL rather than holding Redis
ETA messages; see [Celery's Redis caveats](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html).

## 7. Validation, privacy, and downloads

Propose pypdf for PDF structure and Pillow for images, declared/locked with Boto3,
Celery Redis support, and python-multipart only in later implementation. Choose
compatible maintained versions then; install no optional OCR/rendering stack.

Run parsing in a worker-owned subprocess, with **20-second wall, ten-second CPU,
256 MiB address-space** limits and a private 32 MiB temporary mount; terminate
the subprocess group on timeout/cancellation and always reap it. Use a fixed
entrypoint/arguments, no shell or user-controlled command. Give this subprocess
only its temporary file: close inherited descriptors, pass an allowlisted
environment without credentials, and use a Linux seccomp launcher denying network
syscalls (fail closed if unavailable). A worker
container memory limit and Celery's post-task memory recycling alone do not bound
an individual parser; enforce Linux process limits and verify the subprocess
network restriction in integration. It is containment, not a complete sandbox.

- Inspect magic bytes and parser-detected format; neither extension nor browser
  MIME proves type. A valid supported file with a misleading extension can pass.
  Reject signature/parser disagreement, malformed/truncated content, and unsupported
  containers. Worker repeats size/hash/type checks on bytes actually retrieved.
- PDF: strict structural read, reject any encryption without attempting password
  guessing, and require exactly one actual page, not a filename or untrusted
  page-count hint. Bound all traversal with the subprocess limits. Do not render,
  extract text/images, follow links, fetch URLs, open attachments, or execute
  JavaScript/actions. See [pypdf reader behavior](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html).
- Images: restrict decoders to JPEG/PNG; inspect dimensions/frame count before
  decoding, reject animation/multiple frames, treat decompression-bomb warnings
  as rejection, verify structure, reopen and fully decode within the pixel and
  process limits. Do not enable truncated-image acceptance. See
  [Pillow Image checks](https://pillow.readthedocs.io/en/stable/reference/Image.html).

Parser acceptance is not a malware-free guarantee. Keep all objects private,
including receiving, rejected, and failed files. S3 setup must enable all Block
Public Access controls, Bucket owner enforced ownership (ACLs disabled), HTTPS,
least-privilege access to the configured prefix, and explicit SSE-S3 (`AES256`)
encryption at rest. Do not add ACL-based sharing, public object URLs, credentials
in the browser, or user-selected buckets/paths. See AWS's
[public-access controls](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html),
[disabled ACLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html),
and [SSE-S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html).

For this milestone only accepted documents may be downloaded. After current
authorization and scoped accepted-state lookup, issue a 60-second Boto3 SigV4
presigned GET, bounded also by credential expiry. Force `Content-Disposition:
attachment` with a generated `document-{id}` filename and detected extension,
safe detected content type, and `Cache-Control: no-store`. No inline preview.
Ordinary metadata excludes storage keys, bucket names, leases, ownership tokens,
and upload keys. A presigned URL necessarily reveals its object path and is a
temporary bearer capability: keep it only in memory, never display/log/persist
it, and use `Referrer-Policy: no-referrer`. An already-issued URL can remain
usable until expiry after membership removal; the API cannot recall it by
changing membership. See [AWS presigned URL lifetime/access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html).

Locally, `download_grant` returns a 60-second signed relative URL to
`GET /documents/{id}/local-content?ticket=...`, served only by the local adapter.
This additional delivery route requires the same bearer/workspace authorization,
accepted-state check, and matching unexpired ticket. Use an in-memory API signing
key (restart invalidates tickets); no new persistence table. The browser fetches
the same-origin attachment with its normal headers, then releases its blob URL.
For S3 it navigates to the HTTPS grant without sending application bearer/workspace
headers to S3. Never use the token-bearing API helper for an external URL.
Local delivery rechecks membership and does not prove S3's capability behavior.

Log only server document/job identifiers, allowlisted error/state codes, attempt
numbers, and timings. Never log tokens, contents, filenames, multipart bodies,
credentials, signed URLs/tickets, or raw exceptions. Disable SDK/parser debug and
access/query logging on download paths; preserve current sanitized API errors.

## 8. Permissions and existing authorization integration

| Operation in the selected workspace | Administrator | Accountant | Approver | Non-member |
| --- | --- | --- | --- | --- |
| Upload | Yes | Yes | No | No |
| List/read document metadata, including status/errors | Yes | Yes | Yes | No |
| Read/download accepted file bytes | Yes | Yes | Yes | No |
| Explicitly retry eligible failed processing | Yes | Yes | No | No |
| Download unvalidated/rejected/failed bytes | No | No | No | No |

Reuse exact roles, active-user checks, current membership reads, scoped queries,
and bearer verification from `docs/auth-workspaces.md`. No new role or bypass.
Selecting an inaccessible workspace is generic 403; another workspace's document
under an accessible selection is scoped 404, including download/retry routes.

The current business authorization treats every non-GET as a write. Add a
document-specific operation permission declaration/route class so approvers can
POST `download-url` as a read permission while upload/retry require write
permission. Do not allow all POSTs for approvers or change existing manual APIs.
Authenticate and authorize before multipart parsing. Workers run only the
already-authorized recorded job, resolving workspace/storage key from database
records, not task claims. Later uploader membership removal does not cancel
previously committed validation work; it prevents subsequent API access/grants.

## 9. API contract and representative fictional examples

Paths below are backend paths; browsers prepend `/api`. All five routes require
`Authorization: Bearer <current access token>`, exactly one canonical
`X-Workspace-ID`, and current membership. Responses use `Cache-Control: no-store`.
For upload only, require exactly one canonical UUID `Idempotency-Key` header;
missing/malformed/duplicate values give 422. Other operations reject that header
with 422 so it cannot suggest unsupported replay protection.

| Route | Input and success contract |
| --- | --- |
| `POST /documents` | Multipart field `file` only; header key required. Initial success 202 with document metadata, `Location: /documents/{id}`, `Retry-After: 3`. Replay returns the same ID/current metadata: 202 for nonterminal, 200 terminal, with Location. Never 201 and never an invoice response. |
| `GET /documents` | `limit=20` (1-100), `offset=0` (0-10000); optional single `state` enum filter. Optional `upload_attempt_key` UUID is a recovery filter implicitly restricted to this caller, workspace, and upload operation, returning zero or one item. Reject unknown/repeated query parameters. 200 with existing `items/limit/offset/total` envelope. Filter before counting; order `created_at DESC, id DESC`. |
| `GET /documents/{id}` | UUID path only; 200 metadata below. Polling reads PostgreSQL, never Celery results. |
| `POST /documents/{id}/download-url` | Empty body, no fields; 200 grant with `document_id`, `workspace_id`, `delivery` (`s3_presigned` or `local_authenticated`), `url`, and UTC `expires_at`. Only accepted; other states give 409. No server-side URL fetching. |
| `POST /documents/{id}/retry` | Empty body, no fields. Only failed with retryable processing code, stored finalized bytes, an existing inactive job, `attempt_count=3`, `manual_retry_count=0`, and at least 60 seconds since failure. Lock document then job, recheck, increment manual retry count, clear error/finished time, and atomically queue the same job. Return 202 metadata/Location/Retry-After. All other cases 409; concurrent retries yield one queued result and one conflict. Lost responses are recovered by GET, never automatic POST replay. |

No body/query can set workspace, uploader, document ID, storage key, state, hash,
job, URL target, or attempt counters. List recovery keys are selectors, not access
grants. Offset ordering is deterministic for a fixed dataset, not a snapshot:
new uploads can shift later pages; refresh from page one when needed.

Illustrative request headers/body shape (placeholders, not usable credentials):

```http
POST /documents
Authorization: Bearer <current access token>
X-Workspace-ID: 00000000-0000-4000-8000-000000000001
Idempotency-Key: 60000000-0000-4000-8000-000000000001
Content-Type: multipart/form-data; boundary=fictional-boundary

--fictional-boundary
Content-Disposition: form-data; name="file"; filename="fictional-invoice.pdf"
Content-Type: application/pdf

<generated one-page PDF bytes; this explanatory placeholder is not a file>
--fictional-boundary--
```

202 metadata example; list items and GET detail use this same shape. Nullable
fields remain null until their transition; `can_retry` is a current-caller hint,
rechecked by the backend. Worker acceptance later sets `detected_type="pdf"`,
`state="accepted"`, and `finished_at`, without creating an invoice.

```json
{
  "id": "50000000-0000-4000-8000-000000000001",
  "workspace_id": "00000000-0000-4000-8000-000000000001",
  "uploader_id": "70000000-0000-4000-8000-000000000001",
  "original_filename": "fictional-invoice.pdf",
  "byte_size": 2048,
  "detected_type": null,
  "state": "queued",
  "error_code": null,
  "can_retry": false,
  "created_at": "2026-10-28T09:00:00Z",
  "updated_at": "2026-10-28T09:00:01Z",
  "uploaded_at": "2026-10-28T09:00:01Z",
  "finished_at": null
}
```

Recovery query:
`GET /documents?upload_attempt_key=60000000-0000-4000-8000-000000000001&limit=20&offset=0`.
It returns `{"items":[<metadata above>],"limit":20,"offset":0,"total":1}`
if reservation exists; an empty page does not prove an in-flight request cannot
still reserve. Wait for the upload deadline before offering an explicit resend
of the same file/key. A receiving row is shown/polled while reconciliation runs.

Local grant example, after the same document becomes accepted; the ticket is
fictional. S3 uses the same shape with `delivery="s3_presigned"` and a controlled
bucket HTTPS URL, never a client-supplied target.

```json
{
  "document_id": "50000000-0000-4000-8000-000000000001",
  "workspace_id": "00000000-0000-4000-8000-000000000001",
  "delivery": "local_authenticated",
  "url": "/api/documents/50000000-0000-4000-8000-000000000001/local-content?ticket=FICTIONAL_EXAMPLE",
  "expires_at": "2026-10-28T09:02:00Z"
}
```

Retain `{"error":{"code":...,"message":...,"details":[{"field":...,"message":...}]}}`.
401 `unauthorized` includes `WWW-Authenticate: Bearer`; inactive/unregistered or
insufficient membership/role is 403 `forbidden`; scoped absence is 404 `not_found`;
invalid selector/path/header/multipart/fields is 422 `validation_error`.
Add document-route-only 413 (body/file too large) and 415 (unsupported media/signature
or encoding), both with `validation_error`, not raw framework HTML/errors.
Key reuse, nonaccepted download, and ineligible retry are 409 `conflict`.
Database/JWKS/storage/receive-deadline/capacity failures use sanitized 503
`service_unavailable`; unexpected request failures use 500 `internal_error`.
No terminal upload result is promised on a 503 or lost connection. A known
signature with malformed/encrypted/multipage contents is queued first, then
rejected asynchronously; GET still returns 200 metadata for that rejection.

Representative key conflict (no submitted values echoed):

```json
{
  "error": {
    "code": "conflict",
    "message": "This upload attempt key was already used for another request.",
    "details": [{"field": "idempotency_key", "message": "Use the original file or start a new upload attempt."}]
  }
}
```

Extend only the known safe field labels/error schemas/OpenAPI for document
inputs/statuses. Empty error details remain allowed. Existing health/readiness
bodies/statuses and manual-record errors remain unchanged. Add response validation
for document metadata/grants, including workspace identity, rather than trusting
arbitrary JSON or response URL origins.

## 10. Frontend contract

Add Documents navigation beside Invoices for selected-workspace members, with
`#/documents?limit=20&offset=0`, `#/documents/new`, and `#/documents/{id}`.
Reuse existing pagination, accessible form/error/loading components, private
request context, and route/session generation guards.

| View/control | Behavior |
| --- | --- |
| Upload form | One file picker, accepted formats/5,000,000-byte/single-page guidance, filename/size confirmation, explicit Upload, and disabled repeat-submit guard. Client checks improve feedback; backend/worker enforce limits. No business values or invoice creation. |
| Paginated list | Display filename, upload time, detected type when known, state, and detail link; loading/empty/error/manual refresh and Previous/Next. Optional state filter resets paging. No signed URLs in list data. |
| Detail/status | Show metadata and safe state/code message. `receiving`: "Upload is being finalized." `queued`: "Waiting for file checks; service recovery may delay this." `processing`: "Checking file format and limits." `accepted`: "File checks passed; extraction has not started." `rejected`: "This file does not meet the supported format or limits. Upload a corrected file." `failed`: "File processing could not finish." Map allowlisted codes to useful fixed explanations. |
| Retry | Administrator/accountant only, explicit action when backend `can_retry` is true; explain one remaining cycle. After uncertain retry, GET status before further action. No control for permanent rejection or exhausted lifetime budget. |
| Download | All member roles, accepted only; explicit request for a new short-lived grant. Explain link expiry, fetch local content or navigate to S3 as above, discard URL afterward. No inline preview. |

The existing `privateRequest` JSON/201-only POST assumption cannot handle this
contract. Add a narrow document request adapter or explicit body/expected-status
options: browser `FormData` sets its own boundary (do not set Content-Type), allow
upload 202/terminal-replay 200, retry 202, grant 200, and map safe 413/415.
Retain authentication renewal-before-dispatch, same-origin `/api`, no redirects
for authenticated fetches, current workspace checks, cancellation, and uncertain
write behavior. Only upload uses the explicit 90-second full-operation timeout.

Generate `crypto.randomUUID()` once per chosen file/upload attempt; retain the
key with its original caller/workspace and File only in memory through uncertain
responses. Explicit same-file resends reuse that key; choosing another file or
starting another upload creates a new key. Recover by the caller-scoped list
filter, then detail GET; a 409 must not silently create a new attempt. Full
reload loses this in-memory attempt: inspect the original workspace's list before
starting again and explain the remaining uncertainty.

Cancel polling/uploads and clear File objects, file-input DOM values, object
URLs, previews/blobs, private metadata, and grant URLs on navigation out of the
upload flow, workspace/identity change, membership loss, or logout. Keep only
an in-memory original-workspace uncertainty/key notice where the existing session
permits it, never a File accessible from another workspace. An explicitly resumed
attempt requires the original accessible workspace/caller and reselected file;
the server verifies its fingerprint. Logout clears private attempt information.
No token, file bytes, or document drafts in localStorage/IndexedDB/sessionStorage;
retain sessionStorage solely for existing short-lived PKCE correlation.

Poll only a visible nonterminal detail: every three seconds for five reads, then
every five seconds, at most 20 reads/two minutes per visit, one request at a time
with five-second request deadlines. Stop on accepted/rejected/failed, any error,
navigation/unmount, hidden tab, logout, or workspace/session generation change.
Offer explicit Refresh after the cap/error; resuming a hidden tab requires that
action. Clear timers and reject obsolete completions, not just abort transport.
Role visibility is usability only; backend permissions always apply. Preserve
existing Cognito/PKCE, cancellation, public Status, and all manual form behavior.

## 11. Planned tests and fictional demonstration

All rows below are future verification, not tests run in Step 5.1. Generate
legally usable fictional PDF/JPEG/PNG fixtures; never commit real invoices.
Automated tests must not access AWS, real Cognito, actual environment files, or
the development database. Disable SDK credential/metadata discovery and external
network access in controlled/offline tests. Preserve the exact disposable project-name,
PostgreSQL database/user/version/marker and opt-in guards before any writes.
Use generated signing keys and the real JWT verifier as in existing tests;
inject controlled JWKS/storage transports, never authenticated identities.

| Layer | Required evidence |
| --- | --- |
| Unit/controlled adapters | Deterministic transitions, safe error mapping, fixed clocks/delays, storage failure injection, no sensitive logs. Boto3 request stubs verify checksum/conditional create/encryption/presign parameters without AWS; this is not real S3 proof. Parser fixtures exercise real libraries/subprocess limits, not mocked acceptance. |
| Auth/API with real disposable PostgreSQL | Every role on every route, missing/forged/expired/wrong-client tokens, combined-invalid-input precedence, nonmember 403, other-workspace IDs 404, scoped counts/recovery keys, immediate removal/demotion, and approver download-POST exception without upload/retry permission. Accepted-file downloads/grants only after authorization; no storage-key/workspace overrides or metadata leakage. |
| Upload/validation | Valid generated one-page PDF, JPEG, PNG; exact byte/pixel boundaries; ZIP/unsupported signatures, empty/oversized bodies, malformed multipart/files, encrypted and multi/zero-page PDF, excessive dimensions/decompression bombs, APNG/animation/multi-image JPEG. Missing/understated Content-Length and chunked uploads must stop during parsing, with temp/concurrency bounds. Test cancellation/receive deadlines and cleanup. Misleading extensions/MIME never bypass parser checks. |
| Atomicity/idempotency | Same scoped key/file yields same ID; concurrent replay, changed bytes/name conflict, different caller/workspace keys isolated, identical bytes with new key distinct. Independent PostgreSQL connections prove claims/unique races, paired queued/job commit and rollback, storage success then known/uncertain DB failure, incomplete reservation recovery, stale upload finalization denial, orphan cleanup fencing, and outage-safe no-delete behavior. |
| Job failure recovery | Duplicate task delivery and simultaneous claims, due-time enforcement, attempt budgets/delays, interrupted worker, expired processing/publishing leases, stale attempt completion/retry denial, malformed task IDs, permanent rejection without retry, explicit retry conflicts/cooldown/one-cycle limit. Dispatcher bookkeeping failure after successful publish must remain safe. |
| Real local integration | Actual Celery worker, dispatcher, PostgreSQL, existing Redis broker, shared-volume adapter, real parser, and signed HTTP API in one guarded disposable stack. Pause/stop Redis during upload, restart it; lose a queued message/Redis data only in that disposable broker; interrupt worker after claim; restart dispatcher/API with volumes retained. Prove durable dispatch/lease recovery and one current outcome, without relying on Celery eager mode/mocks. Exercise real local attachment delivery/ticket expiry and no unauthorized bytes. |
| Frontend | Synthetic fetch/session/File tests for FormData/status variants, stable keys, 409/413/415, no automatic writes, uncertain result recovery, generation/cancellation/File clearing, bounded polling, terminal stops, and role controls. Retain existing auth/manual/status tests; separately exercise keyboard, navigation, workspace changes, file reselection, and download behavior in a synthetic local browser demo. |
| Regressions | Fresh/populated additive migration, old records/IDs/decimal totals/seed snapshots unchanged; retain real signed HTTP persistence restart, `/health` independence and unchanged `/ready` PostgreSQL/Redis outage/recovery, frontend tests/lint/build, and disposable cleanup. Worker readiness is checked separately; do not silently change public readiness bodies. |

Independent worker processes cannot see a test's uncommitted savepoints. Use
guarded committed fixtures with targeted cleanup for worker/race integration;
keep existing outer-transaction fixtures for ordinary API tests. Start worker
and dispatcher only after guarded migrations/schema-lifecycle tests finish, and
stop them before schema teardown or retained dependency-outage phases. Extend
`check-backend.ps1`, its shared Python checks, and CI later with the same ordering,
bounded waits, sanitized failure logs, per-project storage volume, and always
cleanup. Unit tests, eager Celery, and mocked storage do not prove broker recovery.

Use a test-only browser harness with controlled OIDC responses and generated,
properly signed access tokens matching the disposable API's JWKS. No production
auth-disable flag, injected authenticated identity, or real Cognito is needed.
Demonstrate: sign in through that harness; select fictional
workspace A; upload one generated file and recover its ID by key; observe queued,
processing, accepted and download; reject a two-page fixture; demonstrate a
controlled temporary outage/recovery and explicit eligible retry; show approver
read/download restrictions and no workspace B leakage; revisit an unchanged
manual draft. Keep scripted transient states observable with controlled gates,
not arbitrary sleeps or claims that every fast state will be visible in a browser.

Real S3 verification is a **later explicitly requested Step 5.6 exercise**:
review cost/current pricing and operator configuration first; then verify private
upload/read, checksum, SSE-S3, public/ACL denial, short-lived attachment GET,
expiry, and the membership-removal caveat using only fictional files in a
controlled prefix. Record real versus stubbed evidence separately and remove
only the designated test objects. It is not a CI prerequisite or authorization
to create resources/read credentials in Step 5.1.

## 12. Costs, limits, and scope review

Documentation and isolated local tests create no cloud charges. Real S3 storage,
requests (including cleanup), and downloads can incur charges; do not assume AWS
credits or free-tier eligibility. Defer AWS setup, region/bucket/IAM configuration,
current official pricing verification, budget/cleanup decisions, and a real S3
check to Step 5.6. No AWS resource is created by this contract.

This is a fictional portfolio demonstration, not a production financial-data
service. Limits include one API/worker initially, bounded local throughput,
single-host volume storage, no malware scanner/content disarm, no OCR or document
accuracy check, no public upload endpoint, no tenant quotas/billing, no immutable
audit/compliance/retention program, and no complete disaster-recovery or enterprise
key-management design. Parser containment and private access reduce exposure but
do not establish those guarantees. Production use needs a separate threat,
capacity, retention, backup/restore, monitoring, and operational review.

No blocking conflict with `scope.md` was found. Decimal 5 MB is now explicit;
10,000,000 pixels is the proposed decoded-image bound. The deliberate integration
changes are the document-specific POST read permission and multipart/202 browser
support. Earlier historical documentation remains intact. PR #3 merge/local-main
synchronization was previously listed as next work; this documentation request
does not perform or verify either action. User review of this contract remains
pending; no implementation step is authorized by preparing it.

## 13. Ordered remaining implementation checklist

Each part requires a separate requested task; complete it before moving onward.

| Part | Purpose and prerequisites | Proposed files/features | Verification and done condition |
| --- | --- | --- | --- |
| **5.2 Schema/migrations** | Persist this reviewed contract. Prerequisite: Step 5.1 review and explicit 5.2 request. | `models/document.py`, `document_job.py`, model exports; new `migrations/versions/0003_documents.py`. No existing migration rewrite or business columns. | Guarded fresh/populated PostgreSQL upgrades, metadata/constraints/indexes, scoped FKs, idempotency uniqueness, rollback and unchanged manual snapshots. Done when additive schema and isolated checks pass with exact results recorded. |
| **5.3 Storage/upload APIs** | Establish private byte lifecycle and scoped HTTP contract. Prerequisite: 5.2 complete. | `storage/` interface/local/S3 adapters; `services/documents.py`, bounded multipart helper, `schemas/document.py`, `api/documents.py`; narrow auth/error/main integration. Lock justified Boto3/python-multipart dependencies here; local volume/configuration and local download delivery. | Controlled storage plus real local-volume/API/PostgreSQL tests for auth, limits, idempotency, atomicity, cleanup, grants. Stub S3 without network. Queued uploads remain durably pending until 5.4. Done when upload/metadata/grants/retry contract is covered without claiming background processing runs. |
| **5.4 Workers/dispatch/recovery** | Turn durable queued work into bounded validation outcomes. Prerequisite: 5.3 complete. | `celery_app.py`, `tasks/documents.py`, `services/document_jobs.py`, isolated validator, `dispatch_documents.py`; lock Celery Redis/pypdf/Pillow; separate worker and dispatcher Compose services using backend image, resource limits and safe config. | Real disposable worker/broker/volume/parser tests, loss/outage/interruption/leases/stale completion/budgets, and receiving/orphan reconciliation. Done when restart recovery and fenced outcomes are demonstrated and unchanged public health/readiness checked. |
| **5.5 Frontend** | Accessible document workflow alongside manual records. Prerequisite: 5.4 APIs/states proven. | `documentApi.ts`, document types/pages, polling hook; narrow `api.ts` options if shared, navigation/App/role controls and synthetic frontend tests. | Tests/lint/build with `SIV_NO_ENV_FILES=1`, role/cancellation/uncertainty/File-isolation coverage and fictional local browser walkthrough. Done when upload through accepted attachment download and rejected/failed/retry paths work, with auth/manual regressions retained. |
| **5.6 Controlled real S3 integration** | Verify the cloud target and actual costs/limits. Prerequisite: local workflow complete, explicit real-S3 request, reviewed operator/cost plan. | Finish/validate S3 process configuration, least-privilege bucket/prefix policy and setup/runbook, controlled verification script if useful; no secrets in Git. Resource creation only when separately authorized. | Current official region-specific pricing review and designated fictional-object checks above; no AWS in automated tests. Done when actual versus mocked evidence, remaining limitations, charges/cleanup boundaries, and operator results are recorded. |
| **5.7 Final verification/CI/merge** | Make the entire milestone repeatable and reviewable. Prerequisite: 5.2-5.6 completed with recorded evidence. | Finalize checker/CI worker orchestration, isolated storage cleanup, generated fixtures/check scripts, README/demo/progress, and review changes. Incremental checks belong in earlier parts too. | Full disposable backend/real HTTP/worker recovery, frontend tests/lint/build and manual demo, safe logs, no unrelated migration/dependency changes, `git diff --check`. Online CI must pass for the separately authorized submitted revision; commit/push/merge require their own authorization. Done only after required verification and explicitly requested merge/synchronization, with evidence and limits recorded. |

Step 5.1 stops with this contract and the progress update. No application tests,
worker/broker/storage integration, browser demonstration, or cloud verification
is claimed by this document.
