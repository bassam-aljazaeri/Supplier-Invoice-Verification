"""Offline S3 fixtures. Synthetic credentials, null config files, no network."""

from io import BytesIO
import os
from threading import Lock

import boto3
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from app.storage.s3 import sdk_config

BUCKET, REGION, PREFIX = "siv-fictional-test", "eu-west-1", "isolated/documents/"


def offline_client(monkeypatch):
    monkeypatch.setenv("AWS_CONFIG_FILE", os.devnull)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", os.devnull)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    session = boto3.session.Session(aws_access_key_id="synthetic-test-id", aws_secret_access_key="synthetic-test-value")
    client = session.client("s3", region_name=REGION, config=sdk_config(), endpoint_url=f"https://s3.{REGION}.amazonaws.com")
    def no_network(**kwargs):
        raise AssertionError("Offline S3 tests cannot send HTTP requests")
    client.meta.events.register("before-send.s3", no_network, unique_id="offline-no-network")
    return client


def response(data):
    class OfflineBody(StreamingBody):
        def set_socket_timeout(self, timeout):
            assert 0 < timeout <= 2
    return {"Body": OfflineBody(BytesIO(data), len(data)), "ContentLength": len(data), "ETag": '"not-a-sha256"'}


class FakeS3:
    """Atomic conditional creation with controllable failures, never a live SDK."""
    def __init__(self):
        self.objects, self.lock, self.calls = {}, Lock(), []
        self.failure = None
        self.after_put = None

    def put_object(self, **params):
        self.calls.append("put")
        assert params["Bucket"] == BUCKET and params["Key"].startswith(PREFIX)
        assert params["IfNoneMatch"] == "*" and params["ServerSideEncryption"] == "AES256"
        with self.lock:
            if self.failure:
                raise self.failure
            if params["Key"] in self.objects:
                raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
            self.objects[params["Key"]] = params["Body"].read()
            if self.after_put:
                raise self.after_put
        return {}

    def get_object(self, **params):
        self.calls.append("get")
        if self.failure:
            raise self.failure
        if params["Key"] not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return response(self.objects[params["Key"]])

    def generate_presigned_url(self, operation, *, Params, ExpiresIn, HttpMethod):
        self.calls.append("presign")
        if self.failure:
            raise self.failure
        assert operation == "get_object" and ExpiresIn == 60 and HttpMethod == "GET"
        assert Params["ResponseContentDisposition"].startswith("attachment;")
        assert Params["ResponseCacheControl"] == "no-store"
        return f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{Params['Key']}?X-Amz-Signature=synthetic"

    def close(self):
        pass
