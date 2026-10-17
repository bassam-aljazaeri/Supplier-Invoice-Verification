"""Synthetic configuration only: no credentials, files, or AWS calls."""

import pytest

from app.cognito import CognitoConfigurationError, configured_issuer


@pytest.mark.parametrize("region", ["eu-west-1", "us-east-2", "us-gov-west-1", "cn-north-1"])
def test_issuer_is_derived_from_region_and_matching_pool(region):
    suffix = "amazonaws.com.cn" if region.startswith("cn-") else "amazonaws.com"
    assert configured_issuer({"COGNITO_REGION": region, "COGNITO_USER_POOL_ID": region + "_EXAMPLE"}) == f"https://cognito-idp.{region}.{suffix}/{region}_EXAMPLE"


@pytest.mark.parametrize("settings", [
    {}, {"COGNITO_REGION": "eu-west-1"}, {"COGNITO_USER_POOL_ID": "eu-west-1_EXAMPLE"},
    {"COGNITO_REGION": "replace-with-cognito-region", "COGNITO_USER_POOL_ID": "replace-with-cognito-user-pool-id"},
    {"COGNITO_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "us-east-1_EXAMPLE"},
    {"COGNITO_REGION": " eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_EXAMPLE"},
    {"COGNITO_REGION": "https://synthetic-private.invalid", "COGNITO_USER_POOL_ID": "EXAMPLE"},
    {"COGNITO_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_EXAMPLE?private"},
    {"COGNITO_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_" + "a" * 56},
])
def test_missing_malformed_and_inconsistent_settings_are_sanitized(settings):
    with pytest.raises(CognitoConfigurationError) as error:
        configured_issuer(settings)
    assert str(error.value) == "Set COGNITO_REGION and a matching COGNITO_USER_POOL_ID before bootstrapping."


def test_arbitrary_issuer_override_is_not_used():
    assert configured_issuer({
        "COGNITO_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_EXAMPLE",
        "COGNITO_ISSUER": "https://untrusted.invalid",
    }) == "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EXAMPLE"
