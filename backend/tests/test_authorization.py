"""Verified signatures plus real current PostgreSQL permissions on protected APIs."""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import create_app
from app.models import ApplicationUser, Supplier, Workspace, WorkspaceMembership
from app.seed_demo import ensure_demo_records, DEMO_SUPPLIER_ID, DEMO_ORDER_ID, DEMO_ORDER_LINE_ID, DEMO_RECEIPT_ID, DEMO_INVOICE_ID
from app.services.identity import ensure_application_user
from app.services.memberships import change_membership_role, ensure_membership
from app.workspace import DEMO_WORKSPACE_ID
from tests.auth_helpers import SETTINGS

pytestmark = pytest.mark.postgres
RECORDS = {"suppliers": DEMO_SUPPLIER_ID, "purchase-orders": DEMO_ORDER_ID, "delivery-receipts": DEMO_RECEIPT_ID, "invoices": DEMO_INVOICE_ID}


def headers(keys, subject, workspace_id=None):
    result = {"Authorization": "Bearer " + keys.token(subject)}
    if workspace_id is not None:
        result["X-Workspace-ID"] = str(workspace_id)
    return result


@pytest.fixture
def access_graph(schema_session, api_client):
    api_client.headers.clear()
    ensure_demo_records(schema_session)
    other = Workspace(slug="other-authorized-company", name="Synthetic other company")
    schema_session.add(other)
    schema_session.flush()
    supplier = Supplier(workspace_id=other.id, supplier_code="OTHER", name="Synthetic other supplier")
    schema_session.add(supplier)
    users = {}
    for subject, role in [("admin", "administrator"), ("accountant", "accountant"), ("approver", "approver"), ("outsider", "administrator")]:
        user = ensure_application_user(schema_session, SETTINGS.issuer, subject)
        users[subject] = user
        ensure_membership(schema_session, other.id if subject == "outsider" else DEMO_WORKSPACE_ID, user.id, role)
    schema_session.commit()
    return api_client, users, other, supplier


@pytest.mark.parametrize("role", ["admin", "accountant", "approver"])
def test_all_roles_read_all_business_records(access_graph, signing_keys, role):
    client, _, _, _ = access_graph
    for resource, record_id in RECORDS.items():
        assert client.get(f"/{resource}", headers=headers(signing_keys, role, DEMO_WORKSPACE_ID)).status_code == 200
        response = client.get(f"/{resource}/{record_id}", headers=headers(signing_keys, role, DEMO_WORKSPACE_ID))
        assert response.status_code == 200 and response.json()["workspace_id"] == str(DEMO_WORKSPACE_ID)


@pytest.mark.parametrize("role", ["admin", "accountant", "approver", "outsider"])
def test_only_creating_roles_can_create_each_business_record(access_graph, signing_keys, role):
    client, _, _, _ = access_graph
    payloads = {
        "suppliers": {"supplier_code": "ROLE-CREATE", "name": "Synthetic create"},
        "purchase-orders": {"supplier_id": str(DEMO_SUPPLIER_ID), "po_number": "ROLE-PO", "order_date": "2026-10-17", "currency": "EUR", "lines": [{"description": "Synthetic", "quantity": "1", "unit_price": "1"}]},
        "delivery-receipts": {"purchase_order_id": str(DEMO_ORDER_ID), "receipt_number": "ROLE-DR", "received_date": "2026-10-17", "lines": [{"purchase_order_line_id": str(DEMO_ORDER_LINE_ID), "quantity_received": "1"}]},
        "invoices": {"supplier_id": str(DEMO_SUPPLIER_ID), "invoice_number": "ROLE-INV", "invoice_date": "2026-10-17", "currency": "EUR", "tax_amount": "0", "lines": [{"description": "Synthetic", "quantity": "1", "unit_price": "1"}]},
    }
    for resource, payload in payloads.items():
        response = client.post(f"/{resource}", headers=headers(signing_keys, role, DEMO_WORKSPACE_ID), json=payload)
        assert response.status_code == (201 if role in {"admin", "accountant"} else 403), response.text


def test_cross_workspace_selection_records_references_and_counts_are_scoped(access_graph, signing_keys):
    client, _, other, supplier = access_graph
    member = headers(signing_keys, "admin", DEMO_WORKSPACE_ID)
    denied = client.get("/suppliers", headers=headers(signing_keys, "admin", other.id))
    absent = client.get("/suppliers", headers=headers(signing_keys, "admin", uuid4()))
    assert denied.status_code == absent.status_code == 403 and denied.json() == absent.json()
    assert client.get(f"/suppliers/{supplier.id}", headers=member).status_code == 404
    assert client.get(f"/suppliers/{uuid4()}", headers=member).status_code == 404
    assert client.get("/suppliers", headers=member).json()["total"] == 1
    assert client.get(f"/purchase-orders?supplier_id={supplier.id}", headers=member).json()["items"] == []
    response = client.post("/purchase-orders", headers=member, json={
        "supplier_id": str(supplier.id), "po_number": "CROSS", "order_date": "2026-10-17", "currency": "EUR",
        "lines": [{"description": "Synthetic", "quantity": "1", "unit_price": "1"}],
    })
    assert response.status_code == 404


@pytest.mark.parametrize("value", [None, "", "bad", " " + str(DEMO_WORKSPACE_ID), str(DEMO_WORKSPACE_ID) + "," + str(DEMO_WORKSPACE_ID)])
def test_selection_is_required_and_malformed_selection_is_422(access_graph, signing_keys, value):
    client, _, _, _ = access_graph
    selected = headers(signing_keys, "admin")
    if value is not None:
        selected["X-Workspace-ID"] = value
    assert client.get("/suppliers", headers=selected).status_code == 422


def test_duplicate_selection_and_role_or_identity_headers_do_not_grant_access(access_graph, signing_keys):
    client, users, _, _ = access_graph
    auth = headers(signing_keys, "admin")
    repeated = list(auth.items()) + [("X-Workspace-ID", str(DEMO_WORKSPACE_ID)), ("X-Workspace-ID", str(DEMO_WORKSPACE_ID))]
    assert client.get("/suppliers", headers=repeated).status_code == 422
    forged = {**headers(signing_keys, "approver", DEMO_WORKSPACE_ID), "X-Role": "administrator", "X-User-ID": str(users["admin"].id), "X-User-Email": "admin@example.invalid"}
    assert client.post("/suppliers", headers=forged, json={"supplier_code": "FORGED", "name": "Synthetic"}).status_code == 403
    signed_roles = headers(signing_keys, "approver", DEMO_WORKSPACE_ID)
    signed_roles["Authorization"] = "Bearer " + signing_keys.token("approver", claims={"role": "administrator", "cognito:groups": ["administrator"]})
    assert client.post("/suppliers", headers=signed_roles, json={}).status_code == 403


@pytest.mark.parametrize("role", ["accountant", "approver", "outsider"])
def test_non_admin_cannot_manage_members_even_with_bad_json(access_graph, signing_keys, role):
    client, users, _, _ = access_graph
    path = f"/workspaces/{DEMO_WORKSPACE_ID}/memberships"
    member = headers(signing_keys, role)
    assert client.get(path, headers=member).status_code == 403
    response = client.post(path, headers={**member, "Content-Type": "application/json"}, content="{")
    assert response.status_code == 403
    assert client.patch(f"{path}/{users['admin'].id}", headers=member, json={"role": "accountant"}).status_code == 403
    assert client.delete(f"{path}/{users['admin'].id}", headers=member).status_code == 403


def test_membership_management_uses_existing_user_ids_and_preserves_last_admin(access_graph, signing_keys):
    client, users, _, _ = access_graph
    admin = headers(signing_keys, "admin")
    path = f"/workspaces/{DEMO_WORKSPACE_ID}/memberships"
    assert client.get(path, headers=admin).json()["total"] == 3
    target = client.get("/me", headers=headers(signing_keys, "new-member")).json()["user"]["id"]
    added = client.post(path, headers=admin, json={"application_user_id": target, "role": "accountant"})
    assert added.status_code == 201 and added.json()["application_user_id"] == target
    assert client.post(path, headers=admin, json={"application_user_id": target, "role": "accountant"}).status_code == 409
    assert client.post(path, headers=admin, json={"email": "unknown@example.invalid", "role": "approver"}).status_code == 422
    assert client.post(path, headers=admin, json={"application_user_id": str(uuid4()), "role": "accountant"}).status_code == 404
    assert client.patch(f"{path}/{target}", headers=admin, json={"role": "owner"}).status_code == 422
    same = client.patch(f"{path}/{target}", headers=admin, json={"role": "accountant"})
    assert same.json()["updated_at"] == added.json()["updated_at"]
    assert client.delete(f"{path}/{users['admin'].id}", headers=admin).status_code == 409
    assert client.patch(f"{path}/{users['admin'].id}", headers=admin, json={"role": "approver"}).status_code == 409
    assert client.patch(f"{path}/{target}", headers=admin, json={"role": "administrator"}).status_code == 200
    removed = client.delete(f"{path}/{users['admin'].id}", headers=admin)
    assert removed.status_code == 204 and removed.content == b""
    assert client.get("/suppliers", headers=headers(signing_keys, "admin", DEMO_WORKSPACE_ID)).status_code == 403


def test_same_token_sees_committed_role_removal_and_inactive_status(access_graph, signing_keys, schema_session):
    client, users, _, _ = access_graph
    admin = headers(signing_keys, "admin")
    existing = headers(signing_keys, "accountant", DEMO_WORKSPACE_ID)
    path = f"/workspaces/{DEMO_WORKSPACE_ID}/memberships/{users['accountant'].id}"
    assert client.get("/suppliers", headers=existing).status_code == 200
    assert client.patch(path, headers=admin, json={"role": "approver"}).status_code == 200
    assert client.post("/suppliers", headers=existing, json={}).status_code == 403
    assert client.delete(path, headers=admin).status_code == 204
    assert client.get("/suppliers", headers=existing).status_code == 403
    users["approver"].is_active = False
    schema_session.commit()
    assert client.get("/suppliers", headers=headers(signing_keys, "approver", DEMO_WORKSPACE_ID)).status_code == 403
    assert client.get("/me", headers=headers(signing_keys, "approver")).status_code == 403
    assert client.post(f"/workspaces/{DEMO_WORKSPACE_ID}/memberships", headers=admin, json={"application_user_id": str(users["approver"].id), "role": "approver"}).status_code == 404


def test_membership_mutation_rechecks_caller_after_waiting_for_lock(postgres_engine, committed_memberships, signing_keys):
    records = committed_memberships
    application = create_app(verifier=signing_keys.verifier())
    started = Queue()

    def session_factory():
        session = Session(postgres_engine, expire_on_commit=False)
        try:
            started.put(session.scalar(text("SELECT pg_backend_pid()")))
            yield session
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    application.dependency_overrides[get_session] = session_factory
    actor_id = records["user_ids"][1]

    def competing_request():
        with TestClient(application, raise_server_exceptions=False) as client:
            return client.post(f"/workspaces/{records['workspace_id']}/memberships", headers=headers(signing_keys, records["subjects"][1]), json={"application_user_id": str(records["user_ids"][2]), "role": "approver"})

    with Session(postgres_engine) as first, ThreadPoolExecutor(max_workers=1) as executor:
        try:
            change_membership_role(first, records["workspace_id"], actor_id, "accountant")
            future = executor.submit(competing_request)
            pid = started.get(timeout=3)
            deadline = time.monotonic() + 2
            while True:
                with postgres_engine.connect() as connection:
                    waiting = connection.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid})
                if waiting == "Lock":
                    break
                assert time.monotonic() < deadline
                time.sleep(0.01)
            first.commit()
            assert future.result(timeout=6).status_code == 403
        finally:
            first.rollback()
    with Session(postgres_engine) as session:
        assert session.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == records["workspace_id"], WorkspaceMembership.application_user_id == records["user_ids"][2])) is None
