"""Private general-purpose S3 objects. Remote orphan deletion is deliberately disabled.

No ETag/metadata is trusted as the application's digest: stat hashes bounded GET
bytes, including on a conditional-create replay. No AWS client exists in local mode.
"""

import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
import threading
import time
from urllib.parse import urlsplit

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage import DownloadGrant, StorageIntegrity, StorageMissing, StorageUnavailable, StoredObject
from app.storage.keys import CHUNK_SIZE, MAX_FILE_SIZE, STORAGE_TIMEOUT, check_key


def sdk_config():
    # One HTTP attempt per operation: durable DB scheduling owns retries.
    return Config(
        signature_version="s3v4", connect_timeout=2, read_timeout=2,
        retries={"mode": "standard", "total_max_attempts": 1},
        s3={"addressing_style": "virtual", "us_east_1_regional_endpoint": "regional", "use_accelerate_endpoint": False},
        use_dualstack_endpoint=False, use_fips_endpoint=False,
        ignore_configured_endpoint_urls=True, max_pool_connections=4,
    )


@contextmanager
def safe_errors():
    try:
        yield
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code == "NoSuchKey":
            raise StorageMissing() from None
        if code in {"BadDigest", "InvalidDigest"}:
            raise StorageIntegrity() from None
        # AccessDenied is infrastructure failure, never evidence of absence.
        raise StorageUnavailable() from None
    except (BotoCoreError, OSError):
        raise StorageUnavailable() from None


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise StorageUnavailable()


class RemoteReader:
    def __init__(self, body, maximum, deadline):
        self.body, self.remaining, self.deadline = body, maximum, deadline

    def read(self, size=-1):
        count = self.remaining + 1 if size < 0 else min(size, self.remaining + 1)
        chunks = []
        while count > 0:
            check_deadline(self.deadline)
            with safe_errors():
                if hasattr(self.body, "set_socket_timeout"):
                    self.body.set_socket_timeout(min(2, self.deadline - time.monotonic()))
                data = self.body.read(min(CHUNK_SIZE, count))
            check_deadline(self.deadline)
            if len(data) > self.remaining:
                raise StorageIntegrity()
            self.remaining -= len(data)
            if not data:
                break
            count -= len(data)
            chunks.append(data)
        return b"".join(chunks)


class S3DocumentStorage:
    def __init__(self, bucket, region, prefix, *, client=None):
        # Deliberately support standard commercial regional HTTPS endpoints only.
        # Dotted buckets, access points, directory buckets and custom endpoints
        # need a separately reviewed origin contract, not implicit SDK fallback.
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket) or bucket.endswith(("--x-s3", "-s3alias", "--ol-s3", ".mrap")):
            raise StorageIntegrity()
        if not re.fullmatch(r"(?:af|ap|ca|eu|il|me|mx|sa|us)-(?!gov-)[a-z]+-\d", region):
            raise StorageIntegrity()
        if not re.fullmatch(r"(?:[a-zA-Z0-9_-]{1,64}/){1,4}", prefix):
            raise StorageIntegrity()
        self.bucket, self.region, self.prefix = bucket, region, prefix
        self.origin = f"https://{bucket}.s3.{region}.amazonaws.com"
        self._sdk, self._lock = client, threading.Lock()

    def _client(self):
        with self._lock:
            if self._sdk is None:
                import boto3
                for name in ("boto3", "botocore", "s3transfer"):
                    logging.getLogger(name).setLevel(logging.WARNING)
                # Use the SDK credential chain. No credentials or endpoint overrides
                # are accepted by the adapter or supplied by a request.
                self._sdk = boto3.session.Session().client(
                    "s3", region_name=self.region, config=sdk_config(),
                    endpoint_url=f"https://s3.{self.region}.amazonaws.com",
                )
                self._sdk.meta.events.register_first("needs-retry.s3", self._deny_region_redirect)
                self._sdk.meta.events.register_first("before-send.s3", self._expected_request)
            return self._sdk

    @staticmethod
    def _deny_region_redirect(response=None, **kwargs):
        # The SDK's S3 region redirector can retry (or HEAD a bucket) separately
        # from the retry budget. Wrong-region configuration must fail closed.
        if response is not None and (response[0].status_code in {301, 302, 307, 308} or response[1].get("Error", {}).get("Code") in {"AuthorizationHeaderMalformed", "PermanentRedirect"}):
            raise StorageUnavailable()

    def _expected_request(self, request, **kwargs):
        parsed = urlsplit(request.url)
        if f"{parsed.scheme}://{parsed.netloc}" != self.origin or not parsed.path.startswith("/" + self.prefix):
            raise StorageIntegrity()

    def _key(self, key):
        check_key(key)
        return self.prefix + key

    @contextmanager
    def _open(self, key, maximum, deadline):
        object_key = self._key(key)
        if not 0 <= maximum <= MAX_FILE_SIZE:
            raise StorageIntegrity()
        check_deadline(deadline)
        with safe_errors():
            response = self._client().get_object(Bucket=self.bucket, Key=object_key)
        body = response["Body"]
        try:
            check_deadline(deadline)
            if not 1 <= response["ContentLength"] <= maximum:
                raise StorageIntegrity()
            yield RemoteReader(body, maximum, deadline)
        finally:
            body.close()

    def open_bounded(self, key, max_bytes):
        return self._open(key, max_bytes, time.monotonic() + STORAGE_TIMEOUT)

    def _stat(self, key, deadline):
        digest, size = hashlib.sha256(), 0
        with self._open(key, MAX_FILE_SIZE, deadline) as source:
            while data := source.read(CHUNK_SIZE):
                size += len(data)
                digest.update(data)
        return StoredObject(size, digest.hexdigest())

    def stat(self, key):
        return self._stat(key, time.monotonic() + STORAGE_TIMEOUT)

    def put_new(self, key, file, size, sha256):
        object_key = self._key(key)
        if not 1 <= size <= MAX_FILE_SIZE or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise StorageIntegrity()
        deadline, actual, digest = time.monotonic() + STORAGE_TIMEOUT, 0, hashlib.sha256()
        with safe_errors():
            file.seek(0)
            while data := file.read(min(CHUNK_SIZE, size - actual + 1)):
                check_deadline(deadline)
                actual += len(data)
                if actual > size:
                    raise StorageIntegrity()
                digest.update(data)
            if actual != size or digest.hexdigest() != sha256:
                raise StorageIntegrity()
            file.seek(0)
            check_deadline(deadline)
            try:
                self._client().put_object(
                    Bucket=self.bucket, Key=object_key, Body=file, ContentLength=size,
                    IfNoneMatch="*", ChecksumSHA256=base64.b64encode(digest.digest()).decode("ascii"),
                    ServerSideEncryption="AES256", ContentType="application/octet-stream", CacheControl="no-store",
                )
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") not in {"PreconditionFailed", "412"}:
                    raise
                # Same key alone is never a replay. Re-read and hash actual bytes.
                if self._stat(key, deadline) != StoredObject(size, sha256):
                    raise StorageIntegrity() from None
            check_deadline(deadline)

    def download_grant(self, document_id, workspace_id, caller_id, expires_in=60, *, storage_key, detected_type):
        if not 1 <= expires_in <= 60 or detected_type not in {"pdf", "jpeg", "png"}:
            raise StorageIntegrity()
        mime, extension = {"pdf": ("application/pdf", "pdf"), "jpeg": ("image/jpeg", "jpg"), "png": ("image/png", "png")}[detected_type]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        with safe_errors():
            url = self._client().generate_presigned_url("get_object", Params={
                "Bucket": self.bucket, "Key": self._key(storage_key),
                "ResponseContentDisposition": f'attachment; filename="document-{document_id}.{extension}"',
                "ResponseContentType": mime, "ResponseCacheControl": "no-store",
            }, ExpiresIn=expires_in, HttpMethod="GET")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != urlsplit(self.origin).netloc or parsed.username or parsed.password or parsed.fragment:
            raise StorageIntegrity()
        # Temporary SDK credentials may expire sooner; the URL cannot outlive them.
        return DownloadGrant(url, expires_at, "s3_presigned")

    def verify_ticket(self, *args):
        return False  # S3 never serves the authenticated local-content route.

    def cleanup_candidates(self):
        return []  # No listing: DB checks cannot fence a delayed remote PUT/delete race.

    def delete_candidate(self, candidate, older_than):
        return False

    def delete(self, key):
        self._key(key)
        raise StorageUnavailable()  # No remote deletion path in Step 5.6A.

    def close(self):
        if self._sdk is not None:
            self._sdk.close()
