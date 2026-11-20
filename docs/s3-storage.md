# Private S3: configuration, verification and limits

Step 5.6A implemented the optional adapter and verified it with controlled local
tests. Step 5.6B user verification is now recorded in [progress](progress.md):
real private S3 upload, processing retry after the streaming-reader fix, Accepted,
and authorized PDF download with matching original/download SHA-256. The user
reported removal of the isolated smoke stack/volumes, dedicated object/bucket,
IAM role and temporary credentials. This is historical operator evidence, not an
AWS check or test rerun performed during Step 5.7 documentation preparation.

**Local storage remains the normal development and CI default.** Automated S3
tests use controlled responses and loopback HTTP without AWS, separately from
that live exercise. Return to the original local stack using
[README's normal startup instructions](../README.md#start-normal-local-development-after-the-s3-smoke-test).
The setup/policy templates below are retained for a separately requested future
repeat; they are not instructions to recreate the removed resources now. Any
repeat needs a designated bucket/prefix, current region-specific pricing,
request/download budget and cleanup review. Do not assume free-tier eligibility.
Use fictional files only. Do not attach S3 to the existing local database or copy
its files: backend selection is per stack, and there is no migration/fallback.

## Required bucket and identity configuration for the later live test

Use a private **general-purpose**, standard regional bucket, with a DNS name
without dots. The supported origin is `https://BUCKET.s3.REGION.amazonaws.com`.
Do not use an S3 website endpoint, access point, directory bucket, acceleration,
China/GovCloud partition or custom endpoint. Bucket and region must agree; the
adapter rejects region redirects. Use a fresh, exclusively owned test prefix,
such as `siv-smoke/run-unique/documents/`, not a shared application's prefix.

- Enable **all four** Block Public Access controls at bucket and account level:
  `BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`.
  See [AWS Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html).
- Set Object Ownership to **Bucket owner enforced**, disabling ACLs. Do not grant
  `PutObjectAcl` or use public ACLs. See [AWS Object Ownership](https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html).
- Set default server-side encryption to **SSE-S3 / AES256**. Every adapter PUT
  also explicitly requests AES256. This step does not use KMS, so no KMS permission
  is needed. See [AWS SSE-S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html).
- Require TLS and conditional/encrypted writes with the bucket-policy fragment
  below. Retain any stricter account policy. No public allow policy, static website,
  bucket CORS or application AWS credential in the browser is required.
- Prefer short-lived workload-role credentials. API, worker and dispatcher must
  each have an available server-side SDK chain. They do not create buckets, set
  policies/encryption/ownership or run migrations at startup. Their credentials
  must outlive the test plus each issued 60-second grant; earlier credential expiry
  also expires the URL. Keep SDK/wire/query logs disabled.

Replace `TEST_BUCKET` and `TEST_PREFIX/` in these **policy templates** with the
designated bucket and dedicated trailing-slash prefix. No credentials belong here.
The API needs only these identity permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyTestObjects",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::TEST_BUCKET/TEST_PREFIX/*"
    },
    {
      "Sid": "CreateOnlyEncryptedTestObjects",
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::TEST_BUCKET/TEST_PREFIX/*",
      "Condition": {
        "StringEquals": {
          "s3:if-none-match": "*",
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

Worker and dispatcher require only the first, `s3:GetObject`, statement on the
same exact prefix. A single isolated smoke identity may combine these two
statements for all three processes. No runtime `ListBucket`, `DeleteObject`, ACL,
bucket-administration, STS administration or wildcard `s3:*` permission is needed.
Without `ListBucket`, an absent key can appear as AccessDenied (503/deferred
reconciliation) rather than NoSuchKey; never infer absence from access denial.

Bucket-policy deny fragment, restricted to the designated test resources:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTestAccess",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": ["arn:aws:s3:::TEST_BUCKET", "arn:aws:s3:::TEST_BUCKET/TEST_PREFIX/*"],
      "Condition": {"Bool": {"aws:SecureTransport": "false"}}
    },
    {
      "Sid": "DenyNonConditionalTestWrites",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::TEST_BUCKET/TEST_PREFIX/*",
      "Condition": {"StringNotEquals": {"s3:if-none-match": "*"}}
    },
    {
      "Sid": "DenyNonSSES3TestWrites",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::TEST_BUCKET/TEST_PREFIX/*",
      "Condition": {"StringNotEquals": {"s3:x-amz-server-side-encryption": "AES256"}}
    }
  ]
}
```

These deny statements grant nobody access. See [AWS conditional-write policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html).
The operator setting up the dedicated bucket separately needs scoped bucket
configuration rights (`s3:PutBucketPublicAccessBlock`, `s3:PutBucketOwnershipControls`,
`s3:PutEncryptionConfiguration`, `s3:PutBucketPolicy`) and corresponding read
rights for inspection on `arn:aws:s3:::TEST_BUCKET`. Account Block Public Access
is an account-administrator responsibility, never a runtime permission. For
post-test inspection/cleanup only, a separate operator may have `s3:ListBucket`
on that bucket with `s3:prefix` limited to `TEST_PREFIX/*`, and `s3:GetObject` /
`s3:DeleteObject` limited to the exact test objects. Existing versioned buckets
also need an explicitly reviewed version cleanup plan and version permissions;
an unversioned dedicated smoke bucket avoids leaving hidden versions. Do not
grant deletion to application processes.

## Exact isolated process configuration for Step 5.6B

The normal Compose file shares `DOCUMENT_STORAGE_BACKEND`, `DOCUMENT_S3_BUCKET`,
`DOCUMENT_S3_REGION` and `DOCUMENT_S3_PREFIX` across API/worker/dispatcher. Defaults
stay local. The CI override **always forces local**, even if these values exist
in the shell. Never change it to test live S3 or run the ordinary disposable
checker against AWS. Use a third, explicit smoke override after both files.

For Docker Desktop, one option is a separately provisioned private directory
outside Git containing only the short-lived smoke profile's standard SDK
`credentials` and `config` files. Do not reuse a directory containing unrelated
accounts, mount your entire user profile, print credential contents, or put them
in a Compose environment/example. The SDK files are consumed only inside the
containers during the later authorized live test. The example below mounts this
chain read-only, uses a synthetic signed HTTP harness and exposes no host API port.
A workload-role deployment can supply its role chain instead of this mount.

After provisioning/review in Step 5.6B, save this **nonsecret override** outside
Git, for example as a temporary `siv-s3-smoke.yaml`:

```yaml
x-smoke-environment: &smoke-environment
  DOCUMENT_STORAGE_BACKEND: s3
  DOCUMENT_S3_BUCKET: ${DOCUMENT_S3_BUCKET:?Set the designated private bucket}
  DOCUMENT_S3_REGION: ${DOCUMENT_S3_REGION:?Set the bucket region}
  DOCUMENT_S3_PREFIX: ${DOCUMENT_S3_PREFIX:?Set a fresh dedicated prefix}
  AWS_SHARED_CREDENTIALS_FILE: /run/siv-aws/credentials
  AWS_CONFIG_FILE: /run/siv-aws/config
  AWS_PROFILE: siv-smoke
  AWS_EC2_METADATA_DISABLED: "true"
x-smoke-chain: &smoke-chain
  type: bind
  source: ${SIV_S3_CHAIN_DIRECTORY:?Set the isolated operator-provisioned directory}
  target: /run/siv-aws
  read_only: true
services:
  api:
    environment: *smoke-environment
    volumes:
      - *smoke-chain
  worker:
    command: [python, -m, app.document_worker]
    environment: *smoke-environment
    volumes:
      - *smoke-chain
  dispatcher:
    environment: *smoke-environment
    volumes:
      - *smoke-chain
```

The following **Windows PowerShell** commands are preparation for that later
exercise, not commands executed in 5.6A. Enter public configuration and paths only.
They create a fresh project/database, never the existing development database.
The explicit generated environment file prevents Compose from loading `.env`.
Python/Alembic commands execute inside the **Linux API container**. This does not
perform a live file smoke test by itself:

```powershell
$s3SmokeProject = 'supplier-invoice-verification-check-' + [Guid]::NewGuid().ToString('N')
$s3SmokeEnvFile = Join-Path ([IO.Path]::GetTempPath()) ($s3SmokeProject + '.env')
$s3SmokeOverride = Read-Host 'Absolute path to reviewed siv-s3-smoke.yaml'
$s3SmokeBucket = Read-Host 'Designated private test bucket'
$s3SmokeRegion = Read-Host 'Exact bucket region'
$s3SmokePrefix = 'siv-smoke/' + [Guid]::NewGuid().ToString('N') + '/documents/'
$s3SmokeChain = Read-Host 'Absolute path to isolated temporary SDK profile directory'
$s3SmokePassword = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
foreach ($s3SmokeName in @('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD',
    'DOCUMENT_S3_BUCKET', 'DOCUMENT_S3_REGION', 'DOCUMENT_S3_PREFIX', 'SIV_S3_CHAIN_DIRECTORY')) {
    if ([Environment]::GetEnvironmentVariable($s3SmokeName, 'Process')) {
        throw 'Use a clean PowerShell session without database/S3 process overrides'
    }
}
$s3SmokeSettings = @(
    'POSTGRES_DB=supplier_invoice_verification_test'
    'POSTGRES_USER=supplier_invoice_verification_test'
    "POSTGRES_PASSWORD=$s3SmokePassword"
    "DOCUMENT_S3_BUCKET=$s3SmokeBucket"
    "DOCUMENT_S3_REGION=$s3SmokeRegion"
    "DOCUMENT_S3_PREFIX=$s3SmokePrefix"
    "SIV_S3_CHAIN_DIRECTORY=$($s3SmokeChain.Replace('\', '/'))"
)
Set-Content -LiteralPath $s3SmokeEnvFile -Value $s3SmokeSettings -Encoding ASCII
$s3SmokeCompose = @('--env-file', $s3SmokeEnvFile, '--project-name', $s3SmokeProject,
    '-f', '.\compose.yaml', '-f', '.\compose.ci.yaml', '-f', $s3SmokeOverride)
function Invoke-S3SmokeCompose {
    param([string[]]$Arguments)
    & docker compose @s3SmokeCompose @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Isolated S3 smoke command failed' }
}
try {
    # Do not print resolved config or credentials.
    Invoke-S3SmokeCompose -Arguments @('config', '--quiet')
    Invoke-S3SmokeCompose -Arguments @('up', '--build', '--detach', '--wait', 'api', 'db', 'redis')
    Invoke-S3SmokeCompose -Arguments @('exec', '-T', 'api', 'python', '-m', 'scripts.check_schema', 'prepare')
    Invoke-S3SmokeCompose -Arguments @('exec', '-T', 'api', 'alembic', 'upgrade', 'head')
    Invoke-S3SmokeCompose -Arguments @('exec', '-T', 'api', 'python', '-m', 'app.seed_workspace')
    Invoke-S3SmokeCompose -Arguments @('exec', '-T', 'api', 'python', '-m', 'scripts.check_auth', 'bootstrap')
    Invoke-S3SmokeCompose -Arguments @('up', '--detach', '--wait', 'worker', 'dispatcher')
    # Run the separately reviewed 5.6B smoke procedure here before teardown.
} finally {
    & docker compose @s3SmokeCompose --profile processing down --volumes --remove-orphans --timeout 10
    if ($LASTEXITCODE -eq 0) { Remove-Item -LiteralPath $s3SmokeEnvFile }
    # This removes only this project's local resources. S3 objects are retained.
}
```

For browser verification in that later task, use an independently configured
isolated API/browser stack and public `VITE_DOCUMENT_S3_ORIGIN` equal to the exact
bucket origin above; preserve the separate synthetic-harness and real-Cognito
evidence. The synthetic no-host-port setup above does not exercise a browser.

## Live verification checklist and evidence limits

The happy-path upload, retry after the reader fix, Accepted status, matching
authorized download and cleanup report above are complete user-reported evidence.
The remaining checklist is retained for any separately requested repeat. Do not
infer verification of every negative permission case, expiry, bucket setting or
charge from the happy-path result; record only what the operator actually checks.

Verify the configured Block Public Access, disabled ACLs, TLS restriction and
AES256 on actual objects with the operator identity. Upload one generated
single-page file through the isolated API; wait for the actual worker to accept
it; verify original size/SHA-256 and conditional-write replay/conflict without
overwrite. Check real missing-object/access-denied responses and recovery without
granting broader runtime permissions. Request grants with current workspace
permissions; verify attachment name/MIME/no-store, credential-free navigation,
anonymous access denial, other-workspace denial and expiry. Revoke a test
membership: new grants must fail, while an already-issued URL can still work
until expiry. Keep URLs/tokens in memory only; do not paste them into logs, Git,
screenshots or shell history. Record live results separately from local simulations.

S3 cleanup listing/deletion remains disabled. Database checks cannot protect
against all delayed remote writes; neither file locks nor age thresholds prove
an S3 orphan is safe to delete. Preserve a manifest of server document IDs and
the designated test keys, stop API/worker/dispatcher, wait for in-flight SDK
operations to finish, then have the separate operator remove **only** those
reviewed test objects/versions and confirm the prefix is clean. Do not delete
the whole bucket, unrelated objects or accepted documents in another stack.
Record actual charges, retained objects and cleanup limitations in progress.md.

This optional backend does not add OCR/extraction or production readiness. The
normal local worker still has Celery's root-user warning, and Linux parser
resource/network restrictions are limited containment, not a complete sandbox or
malware guarantee. Online CI verification of the eventual PR remains Step 5.7.
