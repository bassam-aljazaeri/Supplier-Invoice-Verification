"""Stubber/controlled-fake verification only, never a real AWS integration."""

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import time
from uuid import uuid4

from botocore.exceptions import ReadTimeoutError
from botocore.stub import ANY, Stubber
import pytest

from app.dispatch_documents import Dispatcher
from app.storage import StorageIntegrity, StorageMissing, StorageUnavailable, StoredObject
from app.storage.factory import configured_storage
from app.storage.keys import new_key
from app.storage.s3 import S3DocumentStorage, sdk_config
from tests.s3_helpers import BUCKET, PREFIX, REGION, FakeS3, offline_client, response


@pytest.fixture
def sdk(monkeypatch):
    client = offline_client(monkeypatch)
    try:
        yield client
    finally:
        client.close()


def storage(client):
    return S3DocumentStorage(BUCKET, REGION, PREFIX, client=client)


def values(data=b"fictional private bytes"):
    return new_key(uuid4(), uuid4()), data, hashlib.sha256(data).hexdigest()


def put_params(key, data, digest):
    return {"Bucket": BUCKET, "Key": PREFIX + key, "Body": ANY, "ContentLength": len(data),
            "IfNoneMatch": "*", "ChecksumSHA256": base64.b64encode(bytes.fromhex(digest)).decode(),
            "ServerSideEncryption": "AES256", "ContentType": "application/octet-stream", "CacheControl": "no-store"}


def test_sdk_put_is_conditional_checksummed_encrypted_and_not_multipart(sdk):
    key, data, digest = values()
    with Stubber(sdk) as stub:
        stub.add_response("put_object", {}, put_params(key, data, digest))
        storage(sdk).put_new(key, BytesIO(data), len(data), digest)
        stub.assert_no_pending_responses()
    config = sdk_config()
    assert (config.connect_timeout, config.read_timeout) == (2, 2)
    assert config.retries["total_max_attempts"] == 1 and config.signature_version == "s3v4"
    assert config.ignore_configured_endpoint_urls


@pytest.mark.parametrize("existing", [b"fictional private bytes", b"different private bytes", b"wrong size"])
def test_conditional_replay_hashes_actual_bytes_not_etag_or_metadata(sdk, existing):
    key, data, digest = values()
    result = response(existing)
    result.update(ETag=digest, Metadata={"sha256": digest})
    with Stubber(sdk) as stub:
        stub.add_client_error("put_object", "PreconditionFailed", http_status_code=412, expected_params=put_params(key, data, digest))
        stub.add_response("get_object", result, {"Bucket": BUCKET, "Key": PREFIX + key})
        if existing == data:
            storage(sdk).put_new(key, BytesIO(data), len(data), digest)
        else:
            with pytest.raises(StorageIntegrity):
                storage(sdk).put_new(key, BytesIO(data), len(data), digest)
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("code", ["ConditionalRequestConflict", "AccessDenied", "InternalError", "SlowDown"])
def test_put_failures_are_sanitized_without_blind_retries(sdk, code):
    key, data, digest = values()
    with Stubber(sdk) as stub:
        stub.add_client_error("put_object", code, service_message="fictional-private-diagnostic", expected_params=put_params(key, data, digest))
        with pytest.raises(StorageUnavailable) as error:
            storage(sdk).put_new(key, BytesIO(data), len(data), digest)
        assert str(error.value) == ""
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("code,expected", [("NoSuchKey", StorageMissing), ("AccessDenied", StorageUnavailable), ("NoSuchBucket", StorageUnavailable), ("InternalError", StorageUnavailable)])
def test_get_missing_access_denied_and_outage_are_distinct(sdk, code, expected):
    key, *_ = values()
    with Stubber(sdk) as stub:
        stub.add_client_error("get_object", code, expected_params={"Bucket": BUCKET, "Key": PREFIX + key})
        with pytest.raises(expected):
            storage(sdk).stat(key)
        stub.assert_no_pending_responses()


def test_bounded_get_closes_oversized_response_before_reading(sdk):
    key, data, _ = values()
    result = response(data)
    with Stubber(sdk) as stub:
        stub.add_response("get_object", result, {"Bucket": BUCKET, "Key": PREFIX + key})
        with pytest.raises(StorageIntegrity):
            with storage(sdk).open_bounded(key, len(data) - 1):
                pytest.fail("Oversized object opened")
    assert result["Body"]._raw_stream.closed


def test_streaming_read_failures_are_typed_and_body_is_closed():
    class Broken(BytesIO):
        def read(self, *args):
            raise ReadTimeoutError(endpoint_url="https://fictional.invalid")
    body = Broken()
    class Client:
        def get_object(self, **kwargs):
            return {"Body": body, "ContentLength": 3}
    key, *_ = values()
    with pytest.raises(StorageUnavailable):
        storage(Client()).stat(key)
    assert body.closed


def test_reads_stop_at_byte_and_total_time_bounds(monkeypatch):
    class Client:
        def get_object(self, **kwargs):
            return {"Body": BytesIO(b"1234"), "ContentLength": 3}
    key, *_ = values()
    with storage(Client()).open_bounded(key, 3) as source:
        with pytest.raises(StorageIntegrity):
            source.read()
    with storage(Client()).open_bounded(key, 3) as source:
        monkeypatch.setattr("app.storage.s3.time.monotonic", lambda: source.deadline)
        with pytest.raises(StorageUnavailable):
            source.read(1)


@pytest.mark.parametrize("size,digest", [(0, "a" * 64), (5000001, "a" * 64), (3, "not-sha256"), (3, "a" * 64)])
def test_invalid_put_never_calls_storage(size, digest):
    fake = FakeS3()
    with pytest.raises(StorageIntegrity):
        storage(fake).put_new(new_key(uuid4(), uuid4()), BytesIO(b"123"), size, digest)
    assert not fake.calls


def test_uncertain_success_replay_and_concurrent_conflicts_preserve_original():
    fake, (key, data, digest) = FakeS3(), values()
    adapter = storage(fake)
    fake.after_put = ReadTimeoutError(endpoint_url="https://fictional.invalid")
    with pytest.raises(StorageUnavailable):
        adapter.put_new(key, BytesIO(data), len(data), digest)
    fake.after_put = None
    adapter.put_new(key, BytesIO(data), len(data), digest)
    assert adapter.stat(key) == StoredObject(len(data), digest)
    another = new_key(uuid4(), uuid4())
    def publish(value):
        try:
            adapter.put_new(another, BytesIO(value), len(value), hashlib.sha256(value).hexdigest())
            return True
        except StorageIntegrity:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(publish, [data, data + b"x"])) == [False, True]
    assert fake.objects[PREFIX + key] == data


def test_presigning_uses_real_offline_sigv4_and_safe_response_overrides(sdk, monkeypatch):
    from urllib.parse import parse_qs, urlsplit
    adapter, (key, _, _) = storage(sdk), values()
    doc, ws, caller = uuid4(), uuid4(), uuid4()
    original, params = sdk.generate_presigned_url, []
    def capture(*args, **kwargs):
        params.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(sdk, "generate_presigned_url", capture)
    grant = adapter.download_grant(doc, ws, caller, 60, storage_key=key, detected_type="jpeg")
    url, query = urlsplit(grant.url), parse_qs(urlsplit(grant.url).query)
    assert f"{url.scheme}://{url.netloc}" == adapter.origin and url.path == "/" + PREFIX + key
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"] and query["X-Amz-Expires"] == ["60"]
    assert query["response-content-disposition"] == [f'attachment; filename="document-{doc}.jpg"']
    assert query["response-content-type"] == ["image/jpeg"] and query["response-cache-control"] == ["no-store"]
    assert grant.delivery == "s3_presigned" and 58 <= grant.expires_at.timestamp() - time.time() <= 60
    assert params[0]["Params"]["Key"] == PREFIX + key


@pytest.mark.parametrize("bucket,region,prefix", [("", REGION, PREFIX), ("unsafe.bucket", REGION, PREFIX), (BUCKET, "", PREFIX), (BUCKET, "us-gov-west-1", PREFIX), (BUCKET, REGION, ""), (BUCKET, REGION, "/root/"), (BUCKET, REGION, "../"), (BUCKET, REGION, "prefix")])
def test_configuration_fails_closed(bucket, region, prefix):
    with pytest.raises(StorageIntegrity):
        S3DocumentStorage(bucket, region, prefix)


def test_factory_default_local_and_explicit_s3_never_fall_back(monkeypatch, tmp_path):
    def no_client(*args, **kwargs):
        pytest.fail("Configuration must not discover credentials or create an SDK client")
    monkeypatch.setattr("boto3.session.Session", no_client)
    from app.storage.local import LocalDocumentStorage
    assert isinstance(configured_storage({"DOCUMENT_STORAGE_ROOT": str(tmp_path)}), LocalDocumentStorage)
    with pytest.raises(StorageIntegrity):
        configured_storage({"DOCUMENT_STORAGE_BACKEND": "unknown"})
    with pytest.raises(StorageIntegrity):
        configured_storage({"DOCUMENT_STORAGE_BACKEND": "s3"})
    adapter = configured_storage({"DOCUMENT_STORAGE_BACKEND": "s3", "DOCUMENT_S3_BUCKET": BUCKET, "DOCUMENT_S3_REGION": REGION, "DOCUMENT_S3_PREFIX": PREFIX})
    assert isinstance(adapter, S3DocumentStorage) and adapter._sdk is None


def test_remote_cleanup_never_lists_or_deletes_even_with_stale_candidates():
    from app.storage import StorageCandidate
    class NoRemoteCalls:
        def __getattr__(self, name):
            pytest.fail("Remote cleanup attempted an SDK call")
    class Jobs:
        def candidates(self, kind):
            return []
        def may_delete(self, key):
            pytest.fail("Remote cleanup must not depend on a racy DB check")
    adapter, (key, _, _) = storage(NoRemoteCalls()), values()
    Dispatcher(Jobs(), adapter).step()
    assert adapter.cleanup_candidates() == []
    assert not adapter.delete_candidate(StorageCandidate(key, False, 0, 0, 0), time.time())
    with pytest.raises(StorageUnavailable):
        adapter.delete(key)


@pytest.mark.parametrize("status,code", [(503, "SlowDown"), (301, "PermanentRedirect"), (400, "AuthorizationHeaderMalformed")])
def test_sdk_transport_attempt_budget_and_wrong_region_fail_closed(sdk, monkeypatch, status, code):
    from botocore.awsrequest import AWSResponse
    from types import SimpleNamespace
    adapter = S3DocumentStorage(BUCKET, REGION, PREFIX)
    monkeypatch.setattr("boto3.session.Session", lambda: SimpleNamespace(client=lambda *args, **kwargs: sdk))
    assert adapter._client() is sdk  # Install the same production request guards.
    attempts = []
    class Raw(BytesIO):
        def stream(self, **kwargs):
            yield self.read()
    def send(request):
        attempts.append(request.url)
        return AWSResponse(request.url, status, {"x-amz-bucket-region": "us-east-1"}, Raw(f"<Error><Code>{code}</Code></Error>".encode()))
    monkeypatch.setattr(sdk._endpoint.http_session, "send", send)
    sdk.meta.events.unregister("before-send.s3", unique_id="offline-no-network")
    key, *_ = values()
    with pytest.raises(StorageUnavailable):
        adapter.stat(key)
    assert attempts == [adapter.origin + "/" + PREFIX + key]
