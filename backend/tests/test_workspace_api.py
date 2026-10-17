"""Signed identity/workspace requests, PostgreSQL atomicity, and discovery scope."""

from uuid import UUID

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import ApplicationUser, Workspace, WorkspaceMembership
from app.services import workspaces
from tests.auth_helpers import SETTINGS

pytestmark = pytest.mark.postgres


@pytest.fixture
def client(api_client):
    api_client.headers.clear()
    return api_client


def headers(keys, subject):
    return {"Authorization": "Bearer " + keys.token(subject)}


def test_new_verified_user_gets_own_id_without_any_automatic_membership(client, signing_keys, schema_session):
    member = headers(signing_keys, "new-user")
    assert client.get("/workspaces", headers=member).status_code == 403
    response = client.get("/me", headers=member)
    assert response.status_code == 200
    result = response.json()
    assert set(result["user"]) == {"id", "issuer", "subject", "created_at", "updated_at"}
    assert result["user"]["issuer"] == SETTINGS.issuer and result["user"]["subject"] == "new-user"
    assert result["memberships"] == []
    assert client.get("/me", headers=member).json() == result
    assert client.get("/workspaces", headers=member).json() == {"items": [], "limit": 20, "offset": 0, "total": 0}
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 0
    assert schema_session.scalar(select(func.count()).select_from(ApplicationUser)) == 1


def test_matching_email_claims_do_not_merge_distinct_verified_subjects(client, signing_keys):
    first = client.get("/me", headers={"Authorization": "Bearer " + signing_keys.token("first", claims={"email": "same@example.invalid"})})
    second = client.get("/me", headers={"Authorization": "Bearer " + signing_keys.token("second", claims={"email": "same@example.invalid"})})
    assert first.json()["user"]["id"] != second.json()["user"]["id"]


def test_workspace_creation_is_owned_by_caller_and_discovery_is_scoped(client, signing_keys, schema_session):
    owner = headers(signing_keys, "owner")
    owner_id = client.get("/me", headers=owner).json()["user"]["id"]
    saved = client.post("/workspaces", headers=owner, json={"slug": " synthetic-team ", "name": " Synthetic team "})
    assert saved.status_code == 201, saved.text
    data = saved.json()
    assert data["workspace"]["name"] == "Synthetic team"
    assert data["membership"]["application_user_id"] == owner_id and data["membership"]["role"] == "administrator"
    assert data["membership"]["workspace_id"] == data["workspace"]["id"]
    assert client.get("/me", headers=owner).json()["memberships"][0]["workspace"] == data["workspace"]
    other = headers(signing_keys, "other-owner")
    client.get("/me", headers=other)
    assert client.post("/workspaces", headers=other, json={"slug": "other-team", "name": "Other synthetic team"}).status_code == 201
    listing = client.get("/workspaces?limit=1&offset=0", headers=owner).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == data["workspace"]["id"]
    assert client.get("/workspaces?limit=1&offset=1", headers=owner).json()["items"] == []
    assert client.post("/workspaces", headers=owner, json={"slug": "synthetic-team", "name": "Duplicate"}).status_code == 409
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 2


@pytest.mark.parametrize("payload", [{"slug": "local-demo", "name": "Reserved"}, {"slug": "Bad slug", "name": "Bad"}, {"slug": "valid", "name": " "}, {"slug": "valid", "name": "Valid", "role": "administrator"}, {"slug": "valid", "name": "Valid", "workspace_id": "forged"}])
def test_workspace_input_rejects_reserved_invalid_and_server_fields(client, signing_keys, schema_session, payload):
    owner = headers(signing_keys, "owner")
    client.get("/me", headers=owner)
    assert client.post("/workspaces", headers=owner, json=payload).status_code == 422
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 0


@pytest.mark.parametrize("failure", ["after-membership", "commit"])
def test_workspace_failure_rolls_back_both_rows_and_next_request_recovers(client, signing_keys, schema_session, monkeypatch, failure):
    owner = headers(signing_keys, "owner")
    client.get("/me", headers=owner)
    original = workspaces.ensure_membership

    def fail(*args):
        original(*args)
        raise OperationalError("synthetic-private-sql", None, RuntimeError("synthetic-private-failure"))

    def fail_commit(session):
        raise OperationalError("synthetic-private-sql", None, RuntimeError("synthetic-private-failure"))

    if failure == "after-membership":
        monkeypatch.setattr(workspaces, "ensure_membership", fail)
    else:
        event.listen(Session, "before_commit", fail_commit)
    try:
        response = client.post("/workspaces", headers=owner, json={"slug": "atomic-team", "name": "Synthetic"})
        assert response.status_code == 503 and "synthetic-private" not in response.text
    finally:
        monkeypatch.setattr(workspaces, "ensure_membership", original)
        if failure == "commit":
            event.remove(Session, "before_commit", fail_commit)
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 0
    assert schema_session.scalar(select(func.count()).select_from(WorkspaceMembership)) == 0
    recovered = client.post("/workspaces", headers=owner, json={"slug": "atomic-team", "name": "Synthetic"})
    assert recovered.status_code == 201


def test_workspace_headers_are_rejected_on_identity_and_management_collections(client, signing_keys):
    owner = headers(signing_keys, "owner")
    client.get("/me", headers=owner)
    selected = {**owner, "X-Workspace-ID": "00000000-0000-4000-8000-000000000001"}
    assert client.get("/me", headers=selected).status_code == 422
    assert client.get("/workspaces", headers=selected).status_code == 422
    assert client.post("/workspaces", headers=selected, json={"slug": "new", "name": "Synthetic"}).status_code == 422
