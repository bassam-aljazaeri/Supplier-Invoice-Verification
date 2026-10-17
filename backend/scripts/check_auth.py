"""Guarded synthetic HTTP authentication checks, never a token-minting endpoint."""

import argparse
import os
import subprocess
import sys
from uuid import uuid4

from app.cognito import access_token_settings
from app.db import create_database_engine
from scripts.check_endpoints import read_response
from scripts.check_schema import approved_test_url, require_test_marker, verify_revision
from tests.auth_helpers import HTTP_SUBJECT, SETTINGS, SigningKeys, http_signing_keys

WORKSPACE = "00000000-0000-4000-8000-000000000001"
INVOICE = "40000000-0000-4000-8000-000000000001"
BASE_URL = "http://127.0.0.1:8000"


def require_disposable():
    engine = create_database_engine(approved_test_url(os.environ))
    try:
        with engine.connect() as connection:
            require_test_marker(connection, os.environ)
            verify_revision(connection)
    finally:
        engine.dispose()
    if access_token_settings() != SETTINGS:
        raise RuntimeError("Synthetic Cognito settings are required for disposable HTTP checks.")


def authentication_headers(subject=HTTP_SUBJECT, *, workspace_id=WORKSPACE):
    # Refuse normal development settings before accessing private test artifacts.
    approved_test_url(os.environ)
    if access_token_settings() != SETTINGS:
        raise RuntimeError("Refusing non-synthetic HTTP signing settings.")
    result = {"Authorization": "Bearer " + http_signing_keys().token(subject)}
    if workspace_id is not None:
        result["X-Workspace-ID"] = workspace_id
    return result


def request(path, *, headers=None, payload=None):
    if payload is None:
        return read_response(BASE_URL + path, 5, headers=headers)
    import json
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    operation = Request(BASE_URL + path, data=json.dumps(payload).encode(), headers={
        "Accept": "application/json", "Content-Type": "application/json", **(headers or {}),
    }, method="POST")
    try:
        response = urlopen(operation, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def bootstrap():
    status, me = request("/me", headers=authentication_headers(workspace_id=None))
    if status != 200 or me["user"]["issuer"] != SETTINGS.issuer or me["user"]["subject"] != HTTP_SUBJECT:
        raise RuntimeError("Synthetic signed identity registration failed.")
    result = subprocess.run([
        sys.executable, "-m", "app.bootstrap_membership", "--subject", HTTP_SUBJECT,
        "--workspace-slug", "local-demo", "--role", "administrator",
    ], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError("Explicit disposable membership bootstrap failed.")
    print("Verified synthetic identity registered and explicit demo membership granted.")


def verify():
    status, _ = request("/suppliers")
    if status != 401:
        raise RuntimeError("Live business endpoints did not require authentication.")
    forged = "Bearer " + SigningKeys().token(HTTP_SUBJECT)
    if request("/me", headers={"Authorization": forged})[0] != 401:
        raise RuntimeError("Live verifier did not reject a forged signature.")
    outsider = authentication_headers(HTTP_SUBJECT + "-outsider", workspace_id=None)
    if request("/me", headers=outsider)[0] != 200:
        raise RuntimeError("Synthetic outsider registration failed.")
    if request("/suppliers", headers={**outsider, "X-Workspace-ID": WORKSPACE})[0] != 403:
        raise RuntimeError("Live membership denial was not enforced.")
    member = authentication_headers(workspace_id=None)
    if request("/me", headers=member)[0] != 200:
        raise RuntimeError("Persisted authenticated identity unavailable.")
    status, _ = request("/workspaces", headers=member, payload={"slug": "http-isolation", "name": "Synthetic HTTP isolation"})
    if status not in {201, 409}:
        raise RuntimeError("Synthetic isolation workspace could not be established.")
    status, page = request("/workspaces", headers=member)
    alternatives = [item for item in page.get("items", []) if item["slug"] == "http-isolation"]
    if status != 200 or len(alternatives) != 1:
        raise RuntimeError("Accessible workspace discovery failed.")
    if request("/invoices/" + INVOICE, headers=authentication_headers(workspace_id=alternatives[0]["id"]))[0] != 404:
        raise RuntimeError("Live cross-workspace record isolation failed.")
    if request("/invoices/" + str(uuid4()), headers=authentication_headers())[0] != 404:
        raise RuntimeError("Live scoped missing-record contract failed.")
    print("Live signature verification, 401/403/404 boundaries, and persisted workspace access passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bootstrap", "verify"])
    args = parser.parse_args()
    try:
        require_disposable()
        (bootstrap if args.action == "bootstrap" else verify)()
        return 0
    except Exception:
        print("Disposable authenticated HTTP verification failed; no authentication pass is claimed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
