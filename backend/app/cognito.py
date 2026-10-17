"""Trusted Cognito configuration; no discovery or AWS account calls."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass


class CognitoConfigurationError(ValueError):
    pass


def configured_issuer(settings: Mapping[str, str] | None = None) -> str:
    """Derive the original regional user-pool issuer from trusted configuration."""
    settings = os.environ if settings is None else settings
    region = settings.get("COGNITO_REGION", "")
    pool_id = settings.get("COGNITO_USER_POOL_ID", "")
    if (
        not re.fullmatch(r"[a-z]{2}(?:-[a-z]+){1,3}-[1-9][0-9]*", region)
        or len(pool_id) > 55
        or not re.fullmatch(re.escape(region) + r"_[A-Za-z0-9]+", pool_id)
    ):
        raise CognitoConfigurationError(
            "Set COGNITO_REGION and a matching COGNITO_USER_POOL_ID before bootstrapping."
        )
    suffix = "amazonaws.com.cn" if region.startswith("cn-") else "amazonaws.com"
    return f"https://cognito-idp.{region}.{suffix}/{pool_id}"


@dataclass(frozen=True)
class AccessTokenSettings:
    issuer: str
    client_id: str

    @property
    def jwks_url(self) -> str:
        return self.issuer + "/.well-known/jwks.json"


def access_token_settings(settings: Mapping[str, str] | None = None) -> AccessTokenSettings:
    settings = os.environ if settings is None else settings
    issuer = configured_issuer(settings)
    client_id = settings.get("COGNITO_APP_CLIENT_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9_+]{1,128}", client_id):
        raise CognitoConfigurationError("Set a valid COGNITO_APP_CLIENT_ID before starting the API.")
    return AccessTokenSettings(issuer=issuer, client_id=client_id)
