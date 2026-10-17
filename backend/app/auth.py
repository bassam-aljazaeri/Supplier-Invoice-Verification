"""Access-token verification only. Database membership supplies authorization."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import re
import time

import httpx
import jwt

from app.cognito import AccessTokenSettings

JWKS_TIMEOUT = 3.0
JWKS_MAX_BYTES = 65536
JWKS_CACHE_SECONDS = 300
JWKS_REFRESH_SECONDS = 30


class InvalidCredentials(Exception):
    pass


class JwksUnavailable(Exception):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str


def bearer_token(values: list[str]) -> str:
    if len(values) != 1 or len(values[0]) > 16391:
        raise InvalidCredentials()
    match = re.fullmatch(r"Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", values[0], re.IGNORECASE)
    if match is None:
        raise InvalidCredentials()
    return match.group(1)


async def fetch_jwks(url: str) -> bytes:
    # No proxy/environment configuration, redirects, credentials, or token URLs.
    async with httpx.AsyncClient(timeout=JWKS_TIMEOUT, follow_redirects=False, trust_env=False) as client:
        async with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
            if response.status_code != 200:
                raise JwksUnavailable()
            result = bytearray()
            async for chunk in response.aiter_bytes():
                result.extend(chunk)
                if len(result) > JWKS_MAX_BYTES:
                    raise JwksUnavailable()
            return bytes(result)


class AccessTokenVerifier:
    def __init__(
        self, settings: AccessTokenSettings, *,
        key_source: Callable[[str], Awaitable[bytes]] = fetch_jwks,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self._key_source = key_source
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._last_attempt = float("-inf")
        self._failed = False
        self._lock = asyncio.Lock()

    @staticmethod
    def _parse_keys(raw: bytes) -> dict[str, jwt.PyJWK]:
        try:
            if len(raw) > JWKS_MAX_BYTES:
                raise ValueError()
            document = json.loads(raw)
            if not isinstance(document, dict) or not isinstance(document.get("keys"), list) or not 1 <= len(document["keys"]) <= 20:
                raise ValueError()
            keys = {}
            for item in document["keys"]:
                if not isinstance(item, dict):
                    raise ValueError()
                if item.get("kty") != "RSA" or item.get("alg") != "RS256" or item.get("use") != "sig":
                    continue
                kid = item.get("kid")
                if not isinstance(kid, str) or not kid or len(kid) > 256 or kid != kid.strip() or kid in keys:
                    raise ValueError()
                # A public JWKS must never supply private key material.
                if any(field in item for field in ("d", "p", "q", "dp", "dq", "qi")):
                    raise ValueError()
                key = jwt.PyJWK.from_dict(item, algorithm="RS256")
                if not 2048 <= key.key.key_size <= 4096:
                    raise ValueError()
                keys[kid] = key
            if not keys:
                raise ValueError()
            return keys
        except Exception:
            raise JwksUnavailable() from None

    async def _key(self, kid: str) -> jwt.PyJWK:
        now = self._clock()
        if now < self._expires_at and kid in self._keys:
            return self._keys[kid]
        try:
            # Covers lock waiting, connect, headers, and the complete streamed body.
            async with asyncio.timeout(JWKS_TIMEOUT):
                async with self._lock:
                    now = self._clock()
                    if now < self._expires_at and kid in self._keys:
                        return self._keys[kid]
                    if now - self._last_attempt < JWKS_REFRESH_SECONDS:
                        if self._failed or now >= self._expires_at:
                            raise JwksUnavailable()
                        raise InvalidCredentials()
                    self._last_attempt = now
                    try:
                        keys = self._parse_keys(await self._key_source(self.settings.jwks_url))
                    except Exception:
                        self._failed = True
                        raise JwksUnavailable() from None
                    self._keys = keys
                    self._failed = False
                    self._expires_at = self._clock() + JWKS_CACHE_SECONDS
                    if kid not in keys:
                        raise InvalidCredentials()
                    return keys[kid]
        except TimeoutError:
            self._failed = True
            raise JwksUnavailable() from None

    async def verify(self, token: str) -> VerifiedIdentity:
        try:
            if len(token) > 16384:
                raise InvalidCredentials()
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if header.get("alg") != "RS256" or header.get("crit") or not isinstance(kid, str) or not kid or len(kid) > 256 or kid != kid.strip():
                raise InvalidCredentials()
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise InvalidCredentials() from None
        key = await self._key(kid)
        try:
            claims = jwt.decode(
                token, key.key, algorithms=["RS256"], issuer=self.settings.issuer,
                leeway=30, options={
                    "require": ["iss", "sub", "exp", "iat", "token_use", "client_id"],
                    # Cognito's unbound access-token profile has client_id, no aud.
                    "verify_aud": False,
                },
            )
            subject = claims["sub"]
            if (
                claims["token_use"] != "access" or claims["client_id"] != self.settings.client_id
                or "aud" in claims or not isinstance(subject, str)
                or not 1 <= len(subject) <= 255 or subject != subject.strip()
                or type(claims["exp"]) is not int or type(claims["iat"]) is not int
                or claims["exp"] <= claims["iat"]
                or ("nbf" in claims and type(claims["nbf"]) is not int)
            ):
                raise InvalidCredentials()
            return VerifiedIdentity(issuer=self.settings.issuer, subject=subject)
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
            raise InvalidCredentials() from None
