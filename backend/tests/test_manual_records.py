"""HTTP contracts and committed API writes against guarded disposable PostgreSQL."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import PurchaseOrder, PurchaseOrderLine, Supplier, Workspace
from app.seed_workspace import initialize_workspace
from app.workspace import DEMO_WORKSPACE_ID, DEMO_WORKSPACE_NAME, DEMO_WORKSPACE_SLUG

pytestmark = pytest.mark.postgres
SENSITIVE = "synthetic-private-value-that-must-not-appear-in-errors"


@pytest.fixture
def demo_api(api_client, schema_session):
    initialize_workspace(schema_session)
    return api_client


def supplier_payload(code="DEMO-OFFICE-001", **overrides):
    return {"supplier_code": code, "name": "Demo Office Supplies"} | overrides


def create_supplier(client, code="DEMO-OFFICE-001"):
    response = client.post("/suppliers", json=supplier_payload(code))
    assert response.status_code == 201, response.text
    return response.json()


def order_payload(supplier_id, number="PO-DEMO-001", **overrides):
    return {
        "supplier_id": supplier_id, "po_number": number, "order_date": "2026-10-13",
        "currency": "EUR", "lines": [{"description": "Keyboard", "quantity": "10", "unit_price": "25"}],
    } | overrides


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["details"], list)
    assert SENSITIVE not in response.text
    assert "Traceback" not in response.text
    assert "postgresql://" not in response.text
    assert "INSERT INTO" not in response.text
    assert "Location" not in response.headers


def test_supplier_create_list_retrieve_persistence_and_trimming(demo_api, schema_session):
    response = demo_api.post("/suppliers", json=supplier_payload("  DEMO-OFFICE-001 \t", name=" Demo Office Supplies\n", notes="   "))
    assert response.status_code == 201
    saved = response.json()
    assert response.headers["Location"] == f"/suppliers/{saved['id']}"
    assert saved["supplier_code"] == "DEMO-OFFICE-001"
    assert saved["name"] == "Demo Office Supplies"
    assert saved["notes"] is None
    assert saved["workspace_id"] == str(DEMO_WORKSPACE_ID)
    assert saved["created_at"].endswith("Z")
    assert demo_api.get(response.headers["Location"]).json() == saved
    assert demo_api.get("/suppliers").json() == {"items": [saved], "limit": 20, "offset": 0, "total": 1}
    record = schema_session.get(Supplier, UUID(saved["id"]))
    assert record.name == saved["name"]
    assert record.workspace_id == DEMO_WORKSPACE_ID
    for code, notes in [("OPTIONAL-NULL", None), ("OPTIONAL-TEXT", " synthetic notes ")]:
        result = demo_api.post("/suppliers", json=supplier_payload(code, notes=notes))
        assert result.status_code == 201
        assert result.json()["notes"] == (notes.strip() if notes else None)


def test_order_create_detail_and_header_only_list_persist(demo_api, schema_session):
    supplier = create_supplier(demo_api)
    payload = order_payload(supplier["id"], "  PO-DEMO-001 ", notes=" synthetic order ", lines=[
        {"description": " Keyboard ", "quantity": "10", "unit_price": "25"},
        {"description": "Mouse", "quantity": "0.001", "unit_price": "0"},
    ])
    response = demo_api.post("/purchase-orders", json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert response.headers["Location"] == f"/purchase-orders/{saved['id']}"
    assert saved["po_number"] == "PO-DEMO-001"
    assert saved["notes"] == "synthetic order"
    assert saved["order_date"] == "2026-10-13"
    assert saved["subtotal"] == "250.00"
    assert [line["line_no"] for line in saved["lines"]] == [1, 2]
    assert saved["lines"][0]["quantity"] == "10.000"
    assert saved["lines"][0]["unit_price"] == "25.0000"
    assert saved["lines"][0]["line_total"] == "250.00"
    assert saved["lines"][1]["quantity"] == "0.001"
    assert saved["lines"][1]["unit_price"] == "0.0000"
    assert saved["lines"][1]["line_total"] == "0.00"
    for line in saved["lines"]:
        assert line["workspace_id"] == str(DEMO_WORKSPACE_ID)
        assert line["purchase_order_id"] == saved["id"]
        assert line["created_at"].endswith("Z")
    assert demo_api.get(response.headers["Location"]).json() == saved
    summary = demo_api.get("/purchase-orders").json()
    assert summary["items"] == [{key: value for key, value in saved.items() if key != "lines"}]
    assert summary["total"] == 1
    assert schema_session.get(PurchaseOrder, UUID(saved["id"])).subtotal == Decimal("250.00")
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrderLine)) == 2


def test_per_line_half_up_rounding(demo_api):
    supplier = create_supplier(demo_api)
    response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"], lines=[
        {"description": "Fraction A", "quantity": "0.001", "unit_price": "5"},
        {"description": "Fraction B", "quantity": "0.001", "unit_price": "5"},
    ]))
    assert response.status_code == 201, response.text
    assert [line["line_total"] for line in response.json()["lines"]] == ["0.01", "0.01"]
    assert response.json()["subtotal"] == "0.02"


@pytest.mark.parametrize("kind", ["line", "subtotal"])
def test_calculated_overflow_before_insertion(demo_api, schema_session, kind):
    supplier = create_supplier(demo_api)
    lines = [{"description": "Synthetic large line", "quantity": "999999999.999", "unit_price": "9999999999.9999"}]
    if kind == "subtotal":
        # Each line is within the money limit; adding two exceeds it.
        lines = [{"description": "Synthetic large line", "quantity": "1000000", "unit_price": "9999999999.9999"}] * 2
    response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"], lines=lines))
    assert_error(response, 422, "validation_error")
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrder)) == 0
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrderLine)) == 0
    assert demo_api.post("/purchase-orders", json=order_payload(supplier["id"])).status_code == 201


def test_numeric_bounds_and_maximum_line_count(demo_api):
    supplier = create_supplier(demo_api)
    lines = [{"description": "Bounded quantity", "quantity": "999999999.999", "unit_price": "0"},
             {"description": "Bounded price", "quantity": "0.001", "unit_price": "9999999999.9999"}]
    response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"], lines=lines))
    assert response.status_code == 201, response.text
    assert response.json()["lines"][0]["quantity"] == "999999999.999"
    assert response.json()["lines"][1]["unit_price"] == "9999999999.9999"
    response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"], "HUNDRED", lines=[
        {"description": "Synthetic line", "quantity": "1", "unit_price": "0"}
    ] * 100))
    assert response.status_code == 201, response.text
    assert [line["line_no"] for line in response.json()["lines"]] == list(range(1, 101))


def test_pagination_and_stable_ordering(demo_api, schema_session):
    suppliers = [create_supplier(demo_api, f"S-{index}") for index in range(3)]
    schema_session.execute(update(Supplier).where(Supplier.id == UUID(suppliers[0]["id"])).values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    expected = sorted([row["id"] for row in suppliers[1:]], reverse=True) + [suppliers[0]["id"]]
    page = demo_api.get("/suppliers?limit=2&offset=1").json()
    assert [row["id"] for row in page["items"]] == expected[1:3]
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 1)
    assert demo_api.get("/suppliers?offset=10000").json()["items"] == []
    assert demo_api.get("/purchase-orders").json()["items"] == []
    orders = [demo_api.post("/purchase-orders", json=order_payload(suppliers[index]["id"], f"PO-{index}")).json() for index in range(3)]
    expected = sorted([order["id"] for order in orders], reverse=True)
    page = demo_api.get("/purchase-orders?limit=1&offset=1").json()
    assert [row["id"] for row in page["items"]] == expected[1:2]
    assert page["total"] == 3
    filtered = demo_api.get(f"/purchase-orders?supplier_id={suppliers[1]['id']}").json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == orders[1]["id"]
    assert demo_api.get(f"/purchase-orders?supplier_id={uuid4()}").json()["total"] == 0


@pytest.mark.parametrize("path", ["/suppliers", "/purchase-orders"])
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=1.5", "offset=-1", "offset=10001", "limit=private", "unexpected=value", "workspace_id=value"])
def test_invalid_list_parameters(demo_api, path, query):
    assert_error(demo_api.get(f"{path}?{query}"), 422, "validation_error")


@pytest.mark.parametrize("path", ["/suppliers/not-a-uuid", "/purchase-orders/not-a-uuid", "/purchase-orders?supplier_id=not-a-uuid"])
def test_malformed_uuids_are_validation_errors(demo_api, path):
    assert_error(demo_api.get(path), 422, "validation_error")


@pytest.mark.parametrize("path", ["/suppliers", "/purchase-orders"])
def test_missing_details_are_not_found(demo_api, path):
    assert_error(demo_api.get(f"{path}/{uuid4()}"), 404, "not_found")


def test_workspace_is_required_but_never_created_on_requests(api_client, schema_session):
    for path in ("/suppliers", "/purchase-orders", f"/suppliers/{uuid4()}", f"/purchase-orders/{uuid4()}"):
        assert_error(api_client.get(path), 503, "service_unavailable")
    assert_error(api_client.post("/suppliers", json=supplier_payload()), 503, "service_unavailable")
    assert_error(api_client.post("/purchase-orders", json=order_payload(str(uuid4()))), 503, "service_unavailable")
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 0
    assert api_client.get("/health").json() == {"status": "ok"}


def test_conflicting_demo_workspace_is_unavailable(api_client, schema_session):
    schema_session.add(Workspace(id=DEMO_WORKSPACE_ID, slug=DEMO_WORKSPACE_SLUG, name="Synthetic wrong name"))
    schema_session.commit()
    assert_error(api_client.get("/suppliers"), 503, "service_unavailable")


def test_cross_workspace_records_are_hidden_and_references_rejected(demo_api, schema_session):
    workspace = Workspace(slug="other-workspace", name="Synthetic other workspace")
    schema_session.add(workspace)
    schema_session.flush()
    supplier = Supplier(workspace_id=workspace.id, supplier_code="DEMO-OFFICE-001", name="Synthetic other supplier")
    schema_session.add(supplier)
    schema_session.flush()
    order = PurchaseOrder(workspace_id=workspace.id, supplier_id=supplier.id, po_number="PO-DEMO-001", order_date=datetime(2026, 10, 13).date(), currency="EUR", subtotal=Decimal("0"))
    schema_session.add(order)
    schema_session.commit()
    assert_error(demo_api.get(f"/suppliers/{supplier.id}"), 404, "not_found")
    assert_error(demo_api.get(f"/purchase-orders/{order.id}"), 404, "not_found")
    assert_error(demo_api.post("/purchase-orders", json=order_payload(str(supplier.id))), 404, "not_found")
    for supplier_id in (str(supplier.id), str(uuid4())):
        assert demo_api.get(f"/purchase-orders?supplier_id={supplier_id}").json() == {"items": [], "limit": 20, "offset": 0, "total": 0}
    assert demo_api.get("/suppliers").json()["total"] == 0
    assert demo_api.get("/purchase-orders").json()["total"] == 0
    local_supplier = create_supplier(demo_api)
    assert demo_api.post("/purchase-orders", json=order_payload(local_supplier["id"])).status_code == 201
    assert demo_api.get("/purchase-orders").json()["total"] == 1


def test_missing_supplier_reference(demo_api):
    response = demo_api.post("/purchase-orders", json=order_payload(str(uuid4())))
    assert_error(response, 404, "not_found")
    assert response.json()["error"]["details"][0]["field"] == "supplier_id"


def test_duplicate_constraints_roll_back_and_next_request_succeeds(demo_api, schema_session):
    supplier = create_supplier(demo_api)
    assert_error(demo_api.post("/suppliers", json=supplier_payload()), 409, "conflict")
    assert demo_api.post("/suppliers", json=supplier_payload("RECOVERY")).status_code == 201
    assert demo_api.post("/purchase-orders", json=order_payload(supplier["id"])).status_code == 201
    assert_error(demo_api.post("/purchase-orders", json=order_payload(supplier["id"])), 409, "conflict")
    assert demo_api.post("/purchase-orders", json=order_payload(supplier["id"], "RECOVERY")).status_code == 201
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrder)) == 2
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrderLine)) == 2


@pytest.mark.parametrize("field", ["id", "workspace_id", "created_at", "unexpected", SENSITIVE])
def test_supplier_unknown_and_server_owned_fields_are_rejected(demo_api, field):
    response = demo_api.post("/suppliers", json=supplier_payload(**{field: SENSITIVE}))
    assert_error(response, 422, "validation_error")


@pytest.mark.parametrize("field", ["id", "workspace_id", "created_at", "subtotal", "status", "unexpected"])
def test_order_unknown_and_server_owned_fields_are_rejected(demo_api, field):
    supplier = create_supplier(demo_api)
    assert_error(demo_api.post("/purchase-orders", json=order_payload(supplier["id"], **{field: SENSITIVE})), 422, "validation_error")


@pytest.mark.parametrize("field", ["id", "workspace_id", "created_at", "line_no", "line_total", "purchase_order_id", "unexpected"])
def test_line_unknown_and_server_owned_fields_are_rejected(demo_api, field):
    supplier = create_supplier(demo_api)
    line = {"description": "Keyboard", "quantity": "10", "unit_price": "25", field: SENSITIVE}
    assert_error(demo_api.post("/purchase-orders", json=order_payload(supplier["id"], lines=[line])), 422, "validation_error")


@pytest.mark.parametrize(("field", "value"), [
    ("supplier_code", " "), ("supplier_code", "X" * 65), ("name", "\t"),
    ("name", "X" * 201), ("notes", "X" * 2001), ("name", {"private": SENSITIVE}),
])
def test_supplier_invalid_text_is_not_echoed(demo_api, field, value):
    assert_error(demo_api.post("/suppliers", json=supplier_payload(**{field: value})), 422, "validation_error")


@pytest.mark.parametrize(("field", "value"), [
    ("po_number", " "), ("po_number", "X" * 65), ("order_date", "2026-02-30"),
    ("order_date", "2026-10-13T00:00:00Z"), ("currency", "USD"),
    ("supplier_id", SENSITIVE), ("lines", []),
    ("lines", [{"description": "Keyboard", "quantity": "1", "unit_price": "1"}] * 101),
])
def test_invalid_order_fields(demo_api, field, value):
    supplier = create_supplier(demo_api)
    payload = order_payload(supplier["id"])
    payload[field] = value
    assert_error(demo_api.post("/purchase-orders", json=payload), 422, "validation_error")


@pytest.mark.parametrize(("field", "value"), [
    ("quantity", 10), ("quantity", " 10"), ("quantity", "10 "),
    ("quantity", "+10"), ("quantity", "-10"), ("quantity", "1e1"),
    ("quantity", "NaN"), ("quantity", "Infinity"), ("quantity", "0"),
    ("quantity", "1.0000"), ("quantity", "1000000000"),
    ("unit_price", 25), ("unit_price", "-1"), ("unit_price", "2.5e1"),
    ("unit_price", "1.00000"), ("unit_price", "10000000000"),
    ("description", " "),
])
def test_invalid_line_values_are_indexed(demo_api, field, value):
    supplier = create_supplier(demo_api)
    line = {"description": "Keyboard", "quantity": "10", "unit_price": "25"} | {field: value}
    response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"], lines=[line]))
    assert_error(response, 422, "validation_error")
    assert response.json()["error"]["details"][0]["field"] == f"lines[0].{field}"


def test_malformed_json_is_sanitized(demo_api):
    response = demo_api.post("/suppliers", content='{"name":"' + SENSITIVE + '", broken}', headers={"Content-Type": "application/json"})
    assert_error(response, 422, "validation_error")


def test_failed_later_line_rolls_back_whole_document_and_recovers(demo_api, schema_session):
    supplier = create_supplier(demo_api)
    schema_session.execute(text("""
        CREATE FUNCTION pg_temp.reject_fixture_line() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.line_no = 2 AND NEW.description = 'Synthetic injected failure' THEN
                RAISE EXCEPTION 'synthetic-private-value-that-must-not-appear-in-errors';
            END IF;
            RETURN NEW;
        END $$
    """))
    schema_session.execute(text("""
        CREATE TRIGGER reject_fixture_line BEFORE INSERT ON purchase_order_lines
        FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_fixture_line()
    """))
    lines = [{"description": "Valid first line", "quantity": "1", "unit_price": "25"},
             {"description": "Synthetic injected failure", "quantity": "1", "unit_price": "25"}]
    response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"], lines=lines))
    assert_error(response, 500, "internal_error")
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrder)) == 0
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrderLine)) == 0
    assert demo_api.post("/purchase-orders", json=order_payload(supplier["id"])).status_code == 201


def test_no_success_until_commit_and_unavailable_response_is_sanitized(demo_api, schema_session):
    supplier = create_supplier(demo_api)
    observed = []

    def fail_commit(session):
        observed.append((session.scalar(select(func.count()).select_from(PurchaseOrder)), session.scalar(select(func.count()).select_from(PurchaseOrderLine))))
        raise OperationalError("INSERT INTO secret; postgresql://private", {"private": SENSITIVE}, OSError(SENSITIVE))

    event.listen(Session, "before_commit", fail_commit)
    try:
        response = demo_api.post("/purchase-orders", json=order_payload(supplier["id"]))
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert observed == [(1, 1)]
    assert_error(response, 503, "service_unavailable")
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrder)) == 0
    assert schema_session.scalar(select(func.count()).select_from(PurchaseOrderLine)) == 0
    assert demo_api.post("/purchase-orders", json=order_payload(supplier["id"])).status_code == 201


def test_each_test_starts_without_previous_api_commits(schema_session):
    for model in (Workspace, Supplier, PurchaseOrder, PurchaseOrderLine):
        assert schema_session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("path", ["/approvals", "/exports"])
def test_deferred_business_routes_are_absent(demo_api, path):
    assert demo_api.get(path).status_code == 404
