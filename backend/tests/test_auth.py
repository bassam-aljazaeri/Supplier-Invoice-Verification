"""Real RSA signatures and controlled JWKS; ordinary tests never contact AWS."""

import asyncio
import base64
import json
import time

from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from app import auth
from app.auth import AccessTokenVerifier, InvalidCredentials, JwksUnavailable, bearer_token
from app.cognito import CognitoConfigurationError, access_token_settings
from app.main import create_app
from tests.auth_helpers import SETTINGS, SigningKeys


def verify(verifier, token):
    return asyncio.run(verifier.verify(token))


def test_valid_signature_returns_only_verified_identity_and_ignores_forged_roles():
    keys = SigningKeys()
    result = verify(keys.verifier(), keys.token(claims={"email": "synthetic@example.invalid", "role": "administrator", "workspace_id": "forged"}))
    assert (result.issuer, result.subject) == (SETTINGS.issuer, "synthetic-business-user")
    assert set(result.__dataclass_fields__) == {"issuer", "subject"}


@pytest.mark.parametrize("claims", [
    {"iss": "https://untrusted.invalid/pool"}, {"client_id": "wrongclient"},
    {"token_use": "id"}, {"token_use": "refresh"}, {"sub": ""}, {"sub": " padded"},
    {"sub": "x" * 256}, {"sub": 123}, {"aud": "any-audience"}, {"aud": None},
    {"iat": 1, "exp": 2}, {"iat": True}, {"exp": "9999999999"},
    {"iat": float("inf")}, {"exp": float("inf")}, {"nbf": float("inf")},
    {"iat": int(time.time()) + 1000}, {"nbf": int(time.time()) + 1000}, {"nbf": True},
])
def test_wrong_or_malformed_claims_are_rejected(claims):
    keys = SigningKeys()
    with pytest.raises(InvalidCredentials):
        verify(keys.verifier(), keys.token(claims=claims))


@pytest.mark.parametrize("claim", ["iss", "sub", "exp", "iat", "token_use", "client_id"])
def test_each_required_claim_is_required(claim):
    keys = SigningKeys()
    with pytest.raises(InvalidCredentials):
        verify(keys.verifier(), keys.token(omit=[claim]))


def test_expiration_leeway_is_bounded():
    keys = SigningKeys()
    now = int(time.time())
    assert verify(keys.verifier(), keys.token(claims={"iat": now - 100, "exp": now - 10})).subject
    with pytest.raises(InvalidCredentials):
        verify(keys.verifier(), keys.token(claims={"iat": now - 100, "exp": now - 60}))


def test_forged_signature_and_tampered_payload_are_rejected():
    keys = SigningKeys()
    verifier = keys.verifier()
    with pytest.raises(InvalidCredentials):
        verify(verifier, SigningKeys().token())
    parts = keys.token().split(".")
    parts[1] = base64.urlsafe_b64encode(json.dumps({"sub": "forged"}).encode()).rstrip(b"=").decode()
    with pytest.raises(InvalidCredentials):
        verify(verifier, ".".join(parts))


@pytest.mark.parametrize("component", ["header", "payload"])
def test_deeply_nested_token_json_is_invalid_credentials(component):
    keys = SigningKeys()
    nested = b'{"nested":' + b"[" * 1200 + b"0" + b"]" * 1200 + b"}"
    if component == "header":
        parts = keys.token().split(".")
        parts[0] = base64.urlsafe_b64encode(nested).rstrip(b"=").decode()
        token = ".".join(parts)
    else:
        token = jwt.api_jws.encode(nested, keys.private_key, algorithm="RS256", headers={"kid": keys.kid})
    with pytest.raises(InvalidCredentials):
        verify(keys.verifier(), token)


@pytest.mark.parametrize("algorithm", ["none", "HS256", "RS384"])
def test_unsupported_algorithm_is_rejected_without_key_fetch(algorithm):
    keys = SigningKeys()
    if algorithm == "none":
        token = jwt.encode({"sub": "synthetic"}, key=None, algorithm="none")
    elif algorithm == "HS256":
        token = jwt.encode({"sub": "synthetic"}, key="synthetic-hmac-key-32-characters-long", algorithm=algorithm)
    else:
        token = keys.token(headers={"alg": algorithm})
    with pytest.raises(InvalidCredentials):
        verify(keys.verifier(), token)
    assert keys.calls == []


@pytest.mark.parametrize("values", [[], [""], ["Basic secret"], ["Bearer"], ["Bearer a.b"], ["Bearer a.b.c, Bearer d.e.f"], ["Bearer a.b.c", "Bearer d.e.f"], [" Bearer a.b.c"], ["Bearer " + "x" * 17000]])
def test_malformed_or_multiple_credentials_are_rejected(values):
    with pytest.raises(InvalidCredentials):
        bearer_token(values)


def test_bearer_scheme_is_case_insensitive():
    assert bearer_token(["bearer a.b.c"]) == "a.b.c"


def test_token_urls_are_ignored_and_only_configured_jwks_is_used():
    keys = SigningKeys()
    verify(keys.verifier(), keys.token(headers={"jku": "http://untrusted.invalid/keys", "x5u": "http://untrusted.invalid/cert"}))
    assert keys.calls == [SETTINGS.jwks_url]


def test_cache_rotation_and_unknown_key_refresh_are_bounded():
    first, second = SigningKeys(), SigningKeys("rotated-key")
    ticks = [100.0]
    verifier = first.verifier(clock=lambda: ticks[0])
    verify(verifier, first.token())
    verify(verifier, first.token())
    assert len(first.calls) == 1
    with pytest.raises(InvalidCredentials):
        verify(verifier, second.token())
    assert len(first.calls) == 1
    first.jwks = second.jwks
    ticks[0] += 31
    assert verify(verifier, second.token()).subject
    assert len(first.calls) == 2
    with pytest.raises(InvalidCredentials):
        verify(verifier, first.token())
    assert len(first.calls) == 2


def test_unavailable_keys_fail_closed_expired_cache_is_not_used_and_recovery_works():
    keys = SigningKeys()
    ticks = [100.0]
    verifier = keys.verifier(clock=lambda: ticks[0])
    verify(verifier, keys.token())

    async def unavailable(url):
        raise OSError("synthetic-private-network-detail")

    verifier._key_source = unavailable
    ticks[0] += 301
    with pytest.raises(JwksUnavailable) as error:
        verify(verifier, keys.token())
    assert not str(error.value)
    verifier._key_source = keys.key_source
    with pytest.raises(JwksUnavailable):
        verify(verifier, keys.token())
    ticks[0] += 31
    assert verify(verifier, keys.token()).subject


def test_concurrent_key_fetches_are_coalesced():
    keys = SigningKeys()
    calls = []

    async def source(url):
        calls.append(url)
        await asyncio.sleep(0.01)
        return json.dumps(keys.jwks).encode()

    verifier = AccessTokenVerifier(SETTINGS, key_source=source)

    async def run():
        return await asyncio.gather(*(verifier.verify(keys.token()) for _ in range(20)))

    assert len(asyncio.run(run())) == 20 and calls == [SETTINGS.jwks_url]


def test_full_key_fetch_deadline_cancels_stalled_body(monkeypatch):
    keys = SigningKeys()
    cancelled = []

    async def stalled(url):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(auth, "JWKS_TIMEOUT", 0.02)
    started = time.monotonic()
    with pytest.raises(JwksUnavailable):
        verify(AccessTokenVerifier(SETTINGS, key_source=stalled), keys.token())
    assert time.monotonic() - started < 0.5 and cancelled == [True]


@pytest.mark.parametrize("body", [b"not-json", b"{}", b'{"keys":[]}', b"x" * 65537])
def test_malformed_or_oversized_jwks_is_unavailable(body):
    keys = SigningKeys()

    async def source(url):
        return body

    with pytest.raises(JwksUnavailable):
        verify(AccessTokenVerifier(SETTINGS, key_source=source), keys.token())


@pytest.mark.parametrize("status", [302, 404, 500])
def test_production_transport_rejects_errors_and_redirects_without_following(monkeypatch, status):
    keys = SigningKeys()
    original = httpx.AsyncClient
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status, headers={"Location": "http://untrusted.invalid"}, json={})

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(auth.httpx, "AsyncClient", client)
    with pytest.raises(JwksUnavailable):
        verify(AccessTokenVerifier(SETTINGS), keys.token())
    assert calls == [SETTINGS.jwks_url]


def test_api_401_precedes_invalid_json_and_workspace_and_keeps_challenge():
    keys = SigningKeys()
    with TestClient(create_app(verifier=keys.verifier()), raise_server_exceptions=False) as client:
        for headers in ({}, {"Authorization": "Bearer invalid"}, {"Authorization": "Bearer " + keys.token(claims={"token_use": "id"})}):
            response = client.post("/suppliers?workspace_id=bad", content="{", headers={**headers, "X-Workspace-ID": "bad", "Content-Type": "application/json"})
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["error"]["code"] == "unauthorized"


def test_startup_requires_config_but_does_not_fetch_keys(monkeypatch):
    monkeypatch.setenv("COGNITO_REGION", "eu-west-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-west-1_EXAMPLE")
    monkeypatch.delenv("COGNITO_APP_CLIENT_ID", raising=False)
    with pytest.raises(CognitoConfigurationError):
        with TestClient(create_app()):
            pass
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", SETTINGS.client_id)
    application = create_app()
    with TestClient(application) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert application.state.token_verifier._keys == {}
    assert access_token_settings().jwks_url == SETTINGS.jwks_url


def test_api_distinguishes_unknown_key_401_from_unavailable_jwks_503():
    keys = SigningKeys()
    unknown = SigningKeys("unknown-key")
    with TestClient(create_app(verifier=keys.verifier()), raise_server_exceptions=False) as client:
        assert client.get("/me", headers={"Authorization": "Bearer " + unknown.token()}).status_code == 401

    async def unavailable(url):
        raise OSError("synthetic-private-key-service-detail")

    with TestClient(create_app(verifier=AccessTokenVerifier(SETTINGS, key_source=unavailable)), raise_server_exceptions=False) as client:
        response = client.get("/me", headers={"Authorization": "Bearer " + keys.token()})
        assert response.status_code == 503 and response.json()["error"]["code"] == "service_unavailable"
        assert "synthetic-private" not in response.text and "www-authenticate" not in response.headers


def test_http_harness_refuses_unguarded_target_before_creating_keys(monkeypatch):
    from scripts.check_schema import TestTargetError
    from tests import run_http_api

    monkeypatch.delenv("RUN_POSTGRES_TESTS", raising=False)
    monkeypatch.setattr(run_http_api, "prepare_http_keys", lambda: pytest.fail("Unsafe key file creation."))
    with pytest.raises(TestTargetError):
        run_http_api.main()


def test_http_signing_refuses_unguarded_target_before_reading_private_key(monkeypatch):
    from scripts import check_auth
    from scripts.check_schema import TestTargetError

    monkeypatch.delenv("RUN_POSTGRES_TESTS", raising=False)
    monkeypatch.setattr(check_auth, "http_signing_keys", lambda: pytest.fail("Unsafe private key read."))
    with pytest.raises(TestTargetError):
        check_auth.authentication_headers()
