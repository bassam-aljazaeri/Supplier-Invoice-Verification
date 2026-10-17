"""Generated synthetic signing keys. No real pool, account, token, or AWS call."""

import json
from pathlib import Path
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from app.auth import AccessTokenVerifier
from app.cognito import AccessTokenSettings

SETTINGS = AccessTokenSettings("https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EXAMPLE", "syntheticclient")
BUSINESS_SUBJECT = "synthetic-business-user"
HTTP_SUBJECT = "synthetic-http-demo-user"
KEY_DIRECTORY = Path("/tmp/supplier-invoice-verification-auth")


class SigningKeys:
    def __init__(self, kid="synthetic-key", private_key=None):
        self.kid = kid
        self.private_key = private_key or rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        public.update(kid=kid, use="sig", alg="RS256")
        self.jwks = {"keys": [public]}
        self.calls = []

    def token(self, subject=BUSINESS_SUBJECT, *, claims=None, headers=None, omit=()):
        now = int(time.time())
        payload = {"iss": SETTINGS.issuer, "sub": subject, "iat": now, "exp": now + 900, "token_use": "access", "client_id": SETTINGS.client_id}
        payload.update(claims or {})
        for field in omit:
            payload.pop(field, None)
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": self.kid, **(headers or {})})

    async def key_source(self, url):
        if url != SETTINGS.jwks_url:
            raise AssertionError("Refusing a key URL outside the synthetic configured issuer.")
        self.calls.append(url)
        return json.dumps(self.jwks).encode()

    def verifier(self, **kwargs):
        return AccessTokenVerifier(SETTINGS, key_source=self.key_source, **kwargs)


def prepare_http_keys():
    """Only a guarded disposable entrypoint may call this file-writing helper."""
    KEY_DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    KEY_DIRECTORY.chmod(0o700)
    private_path = KEY_DIRECTORY / "private.pem"
    public_path = KEY_DIRECTORY / "public.json"
    if private_path.exists() and public_path.exists():
        return
    keys = SigningKeys()
    private_path.write_bytes(keys.private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ))
    private_path.chmod(0o600)
    public_path.write_text(json.dumps(keys.jwks), encoding="utf-8")
    public_path.chmod(0o600)


def http_signing_keys():
    private = serialization.load_pem_private_key((KEY_DIRECTORY / "private.pem").read_bytes(), password=None)
    return SigningKeys(private_key=private)


async def http_public_keys(url):
    if url != SETTINGS.jwks_url:
        raise AssertionError("Refusing an unexpected synthetic JWKS URL.")
    return (KEY_DIRECTORY / "public.json").read_bytes()
