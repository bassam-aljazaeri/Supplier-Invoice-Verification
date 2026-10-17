"""Separate disposable-only HTTP entrypoint. No production setting can select it."""

import os

import uvicorn

from app.auth import AccessTokenVerifier
from app.cognito import access_token_settings
from app.main import create_app
from scripts.check_schema import approved_test_url
from tests.auth_helpers import SETTINGS, http_public_keys, prepare_http_keys


def main():
    # Settings guard before touching test key files. Database marker guards still
    # precede every migration/test/seed/grant; health works before migrations.
    approved_test_url(os.environ)
    if access_token_settings() != SETTINGS:
        raise RuntimeError("Disposable HTTP checks require the exact synthetic Cognito settings.")
    prepare_http_keys()
    application = create_app(verifier=AccessTokenVerifier(SETTINGS, key_source=http_public_keys))
    uvicorn.run(application, host="0.0.0.0", port=8000, access_log=False)


if __name__ == "__main__":
    main()
