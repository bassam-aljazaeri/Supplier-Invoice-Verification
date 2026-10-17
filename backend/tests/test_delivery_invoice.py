"""Committed delivery and draft-invoice APIs on explicitly guarded PostgreSQL."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import (
    DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine, PurchaseOrder,
    PurchaseOrderLine, Supplier, Workspace,
)
from app.seed_workspace import initialize_workspace
from app.workspace import DEMO_WORKSPACE_ID

pytestmark = pytest.mark.postgres
PRIVATE = "synthetic-private-value-that-must-not-appear-in-errors"


def assert_error(response, status, code, field=None):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert set(response.json()) == {"error"}
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == code
    assert isinstance(error["details"], list)
    if field is not None:
        assert error["details"][0]["field"] == field
    for value in (PRIVATE, "Traceback", "postgresql://", "INSERT INTO"):
        assert value not in response.text
    assert "Location" not in response.headers


def supplier(client, code="SUP-001"):
    response = client.post("/suppliers", json={"supplier_code": code, "name": "Fictional supplier"})
    assert response.status_code == 201, response.text
    return response.json()


def order(client, supplier_id, number="PO-001", lines=None):
    response = client.post("/purchase-orders", json={
        "supplier_id": supplier_id, "po_number": number, "order_date": "2026-10-13", "currency": "EUR",
        "lines": lines or [{"description": "Keyboard", "quantity": "10", "unit_price": "25"}],
    })
    assert response.status_code == 201, response.text
    return response.json()


def receipt_payload(po, number="DR-001", **overrides):
    return {
        "purchase_order_id": po["id"], "receipt_number": number, "received_date": "2026-10-14",
        "lines": [{"purchase_order_line_id": po["lines"][0]["id"], "quantity_received": "8"}],
    } | overrides


def invoice_payload(supplier_id, number="INV-001", **overrides):
    return {
        "supplier_id": supplier_id, "invoice_number": number, "invoice_date": "2026-10-15",
        "currency": "EUR", "tax_amount": "0",
        "lines": [{"description": "Keyboard", "quantity": "10", "unit_price": "25"}],
    } | overrides


@pytest.fixture
def demo_api(api_client, schema_session, grant_demo_access):
    initialize_workspace(schema_session)
    grant_demo_access()
    return api_client


@pytest.fixture
def records(demo_api):
    vendor = supplier(demo_api)
    return vendor, order(demo_api, vendor["id"])


@pytest.fixture
def foreign_records(schema_session):
    workspace = Workspace(slug="other-workspace", name="Fictional other workspace")
    schema_session.add(workspace)
    schema_session.flush()
    vendor = Supplier(workspace_id=workspace.id, supplier_code="FOREIGN", name="Fictional foreign supplier")
    schema_session.add(vendor)
    schema_session.flush()
    po = PurchaseOrder(workspace_id=workspace.id, supplier_id=vendor.id, po_number="FOREIGN", order_date=date(2026, 10, 13), currency="EUR", subtotal=Decimal("25"), lines=[
        PurchaseOrderLine(workspace_id=workspace.id, line_no=1, description="Fictional line", quantity=Decimal("1"), unit_price=Decimal("25"), line_total=Decimal("25")),
    ])
    schema_session.add(po)
    schema_session.flush()
    receipt = DeliveryReceipt(workspace_id=workspace.id, purchase_order_id=po.id, receipt_number="FOREIGN", received_date=date(2026, 10, 14), lines=[
        DeliveryReceiptLine(workspace_id=workspace.id, purchase_order_id=po.id, purchase_order_line_id=po.lines[0].id, line_no=1, quantity_received=Decimal("1")),
    ])
    invoice = Invoice(workspace_id=workspace.id, supplier_id=vendor.id, purchase_order_id=po.id, invoice_number="FOREIGN", invoice_date=date(2026, 10, 15), currency="EUR", subtotal=Decimal("25"), tax_amount=Decimal("0"), total=Decimal("25"), lines=[
        InvoiceLine(workspace_id=workspace.id, line_no=1, description="Fictional line", quantity=Decimal("1"), unit_price=Decimal("25"), line_total=Decimal("25"), purchase_order_id=po.id, purchase_order_line_id=po.lines[0].id),
    ])
    schema_session.add_all([receipt, invoice])
    schema_session.commit()
    return vendor, po, receipt, invoice


def count(session, model):
    return session.scalar(select(func.count()).select_from(model).where(model.workspace_id == DEMO_WORKSPACE_ID))


def test_ordered_ten_delivered_eight_invoiced_ten_persistence(demo_api, records, schema_session):
    vendor, po = records
    response = demo_api.post("/delivery-receipts", json=receipt_payload(po, " DR-001 ", notes="  "))
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert response.headers["Location"] == f"/delivery-receipts/{receipt['id']}"
    assert receipt["receipt_number"] == "DR-001"
    assert receipt["notes"] is None
    assert receipt["received_date"] == "2026-10-14"
    line = receipt["lines"][0]
    assert (line["line_no"], line["quantity_received"]) == (1, "8.000")
    assert line["delivery_receipt_id"] == receipt["id"]
    assert line["purchase_order_id"] == po["id"]
    assert line["purchase_order_line_id"] == po["lines"][0]["id"]
    assert demo_api.get(response.headers["Location"]).json() == receipt
    payload = invoice_payload(vendor["id"], " INV-001 ", purchase_order_id=po["id"], due_date="2026-11-15", notes=" synthetic invoice ")
    payload["lines"][0].update(description=" Keyboard ", purchase_order_line_id=po["lines"][0]["id"])
    response = demo_api.post("/invoices", json=payload)
    assert response.status_code == 201, response.text
    invoice = response.json()
    assert response.headers["Location"] == f"/invoices/{invoice['id']}"
    assert invoice["invoice_number"] == "INV-001"
    assert invoice["notes"] == "synthetic invoice"
    assert invoice["status"] == "draft"
    assert (invoice["subtotal"], invoice["tax_amount"], invoice["total"]) == ("250.00", "0.00", "250.00")
    line = invoice["lines"][0]
    assert (line["line_no"], line["quantity"], line["unit_price"], line["line_total"]) == (1, "10.000", "25.0000", "250.00")
    assert line["description"] == "Keyboard"
    assert line["invoice_id"] == invoice["id"]
    assert "purchase_order_id" not in line
    assert demo_api.get(response.headers["Location"]).json() == invoice
    for resource, saved in [("delivery-receipts", receipt), ("invoices", invoice)]:
        assert saved["workspace_id"] == str(DEMO_WORKSPACE_ID)
        assert saved["created_at"].endswith("Z")
        assert all(item["workspace_id"] == str(DEMO_WORKSPACE_ID) and item["created_at"].endswith("Z") for item in saved["lines"])
        listing = demo_api.get(f"/{resource}?purchase_order_id={po['id']}").json()
        assert listing == {"items": [{key: value for key, value in saved.items() if key != "lines"}], "limit": 20, "offset": 0, "total": 1}
    stored_receipt = schema_session.get(DeliveryReceipt, UUID(receipt["id"]))
    stored_invoice = schema_session.get(Invoice, UUID(invoice["id"]))
    assert stored_receipt.lines[0].quantity_received == Decimal("8")
    assert stored_invoice.lines[0].quantity == Decimal("10")
    assert stored_invoice.lines[0].purchase_order_id == UUID(po["id"])
    assert stored_invoice.lines[0].purchase_order_line.description == "Keyboard"
    assert stored_receipt.lines[0].purchase_order_line.quantity == Decimal("10")
    assert stored_invoice.purchase_order.id == stored_receipt.purchase_order.id


def test_multiple_receipts_and_overdelivery_are_allowed(demo_api, records):
    _, po = records
    for index, quantity in enumerate(("8", "8", "999999999.999", "0.001")):
        payload = receipt_payload(po, f"DR-{index}")
        payload["lines"][0]["quantity_received"] = quantity
        response = demo_api.post("/delivery-receipts", json=payload)
        assert response.status_code == 201, response.text
        assert response.json()["lines"][0]["quantity_received"] == format(Decimal(quantity), ".3f")
    assert demo_api.get(f"/delivery-receipts?purchase_order_id={po['id']}").json()["total"] == 4


def test_duplicate_receipt_lines_rejected_without_partial_save(demo_api, records, schema_session):
    _, po = records
    payload = receipt_payload(po)
    payload["lines"] *= 2
    assert_error(demo_api.post("/delivery-receipts", json=payload), 422, "validation_error", "lines[1].purchase_order_line_id")
    assert count(schema_session, DeliveryReceipt) == count(schema_session, DeliveryReceiptLine) == 0
    assert demo_api.post("/delivery-receipts", json=receipt_payload(po)).status_code == 201


@pytest.mark.parametrize(("has_order", "mapping"), [(False, "omitted"), (False, "null"), (True, "omitted"), (True, "null"), (True, "mapped")])
def test_optional_invoice_order_and_mapping_combinations(demo_api, records, schema_session, has_order, mapping):
    vendor, po = records
    payload = invoice_payload(vendor["id"])
    if has_order:
        payload["purchase_order_id"] = po["id"]
    elif mapping == "null":
        payload["purchase_order_id"] = None
    if mapping != "omitted":
        payload["lines"][0]["purchase_order_line_id"] = po["lines"][0]["id"] if mapping == "mapped" else None
    response = demo_api.post("/invoices", json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["purchase_order_id"] == (po["id"] if has_order else None)
    assert saved["due_date"] is None and saved["notes"] is None
    line = schema_session.get(Invoice, UUID(saved["id"])).lines[0]
    assert line.purchase_order_id == (UUID(po["id"]) if mapping == "mapped" else None)
    assert line.purchase_order_line_id == (UUID(po["lines"][0]["id"]) if mapping == "mapped" else None)
    assert saved["lines"][0]["purchase_order_line_id"] == (po["lines"][0]["id"] if mapping == "mapped" else None)


def test_mixed_unmapped_and_repeated_mappings_and_price_difference_allowed(demo_api, records):
    vendor, po = records
    lines = [
        {"description": "Unmapped", "quantity": "12", "unit_price": "26"},
        {"description": "Mapped A", "quantity": "10", "unit_price": "25", "purchase_order_line_id": po["lines"][0]["id"]},
        {"description": "Mapped B", "quantity": "1", "unit_price": "25", "purchase_order_line_id": po["lines"][0]["id"]},
    ]
    response = demo_api.post("/invoices", json=invoice_payload(vendor["id"], purchase_order_id=po["id"], lines=lines))
    assert response.status_code == 201, response.text
    saved = response.json()
    assert [line["line_no"] for line in saved["lines"]] == [1, 2, 3]
    assert demo_api.get(response.headers["Location"]).json() == saved
    assert saved["subtotal"] == "587.00"


def test_invoice_round_each_line_then_add_explicit_tax(demo_api, records):
    vendor, _ = records
    response = demo_api.post("/invoices", json=invoice_payload(vendor["id"], tax_amount="0.01", due_date="2026-10-15", lines=[
        {"description": "Fraction A", "quantity": "0.001", "unit_price": "5"},
        {"description": "Fraction B", "quantity": "0.001", "unit_price": "5"},
    ]))
    assert response.status_code == 201, response.text
    saved = response.json()
    assert [line["line_total"] for line in saved["lines"]] == ["0.01", "0.01"]
    assert (saved["subtotal"], saved["tax_amount"], saved["total"]) == ("0.02", "0.01", "0.03")


@pytest.mark.parametrize("kind", ["line", "subtotal", "total"])
def test_invoice_calculated_overflow_before_insert_and_recovery(demo_api, records, schema_session, kind):
    vendor, _ = records
    lines = [{"description": "Large fictional line", "quantity": "999999999.999", "unit_price": "9999999999.9999"}]
    tax = "0"
    if kind == "subtotal":
        lines = [{"description": "Large fictional line", "quantity": "1000000", "unit_price": "9999999999.9999"}] * 2
    if kind == "total":
        lines = [{"description": "Fictional cent", "quantity": "1", "unit_price": "0.01"}]
        tax = "9999999999999999.99"
    assert_error(demo_api.post("/invoices", json=invoice_payload(vendor["id"], lines=lines, tax_amount=tax)), 422, "validation_error")
    assert count(schema_session, Invoice) == count(schema_session, InvoiceLine) == 0
    assert demo_api.post("/invoices", json=invoice_payload(vendor["id"])).status_code == 201


def test_invoice_input_bounds_and_maximum_line_count(demo_api, records):
    vendor, _ = records
    lines = [{"description": "Max quantity", "quantity": "999999999.999", "unit_price": "0"}]
    response = demo_api.post("/invoices", json=invoice_payload(vendor["id"], tax_amount="9999999999999999.99", lines=lines))
    assert response.status_code == 201, response.text
    assert response.json()["total"] == "9999999999999999.99"
    assert response.json()["lines"][0]["quantity"] == "999999999.999"
    response = demo_api.post("/invoices", json=invoice_payload(vendor["id"], "MAX-PRICE", lines=[
        {"description": "Max price", "quantity": "0.001", "unit_price": "9999999999.9999"},
    ]))
    assert response.status_code == 201, response.text
    assert response.json()["lines"][0]["unit_price"] == "9999999999.9999"
    response = demo_api.post("/invoices", json=invoice_payload(vendor["id"], "HUNDRED", lines=[
        {"description": "Fictional line", "quantity": "1", "unit_price": "0"},
    ] * 100))
    assert response.status_code == 201, response.text
    assert [line["line_no"] for line in response.json()["lines"]] == list(range(1, 101))


def test_receipt_one_hundred_ordered_lines_and_ordered_detail(demo_api, records):
    vendor, _ = records
    po = order(demo_api, vendor["id"], "HUNDRED", lines=[{"description": "Fictional line", "quantity": "1", "unit_price": "0"}] * 100)
    payload = receipt_payload(po, lines=[{"purchase_order_line_id": line["id"], "quantity_received": "1"} for line in reversed(po["lines"])])
    response = demo_api.post("/delivery-receipts", json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert [line["line_no"] for line in saved["lines"]] == list(range(1, 101))
    assert [line["purchase_order_line_id"] for line in saved["lines"]] == [line["id"] for line in reversed(po["lines"])]
    assert demo_api.get(response.headers["Location"]).json() == saved


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
@pytest.mark.parametrize("source", ["missing", "foreign", "wrong_order"])
def test_line_references_missing_foreign_or_another_order(demo_api, records, foreign_records, schema_session, resource, source):
    vendor, po = records
    line_id = str(uuid4())
    if source == "foreign":
        line_id = str(foreign_records[1].lines[0].id)
    elif source == "wrong_order":
        line_id = order(demo_api, vendor["id"], "OTHER")["lines"][0]["id"]
    if resource == "delivery-receipts":
        payload = receipt_payload(po)
        header, line_model = DeliveryReceipt, DeliveryReceiptLine
    else:
        payload = invoice_payload(vendor["id"], purchase_order_id=po["id"])
        header, line_model = Invoice, InvoiceLine
    payload["lines"][0]["purchase_order_line_id"] = line_id
    status, code = (422, "validation_error") if source == "wrong_order" else (404, "not_found")
    assert_error(demo_api.post(f"/{resource}", json=payload), status, code, "lines[0].purchase_order_line_id")
    assert count(schema_session, header) == count(schema_session, line_model) == 0


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
@pytest.mark.parametrize("foreign", [False, True])
def test_order_reference_missing_or_cross_workspace(demo_api, records, foreign_records, resource, foreign):
    vendor, po = records
    order_id = str(foreign_records[1].id) if foreign else str(uuid4())
    payload = receipt_payload(po, purchase_order_id=order_id) if resource == "delivery-receipts" else invoice_payload(vendor["id"], purchase_order_id=order_id)
    assert_error(demo_api.post(f"/{resource}", json=payload), 404, "not_found", "purchase_order_id")


@pytest.mark.parametrize("foreign", [False, True])
def test_invoice_supplier_missing_or_foreign(demo_api, foreign_records, foreign):
    supplier_id = str(foreign_records[0].id) if foreign else str(uuid4())
    assert_error(demo_api.post("/invoices", json=invoice_payload(supplier_id)), 404, "not_found", "supplier_id")


def test_invoice_order_must_belong_to_selected_supplier(demo_api, records):
    _, po = records
    other = supplier(demo_api, "OTHER")
    assert_error(demo_api.post("/invoices", json=invoice_payload(other["id"], purchase_order_id=po["id"])), 422, "validation_error", "purchase_order_id")


def test_invoice_without_order_cannot_map_lines(demo_api, records, schema_session):
    vendor, po = records
    payload = invoice_payload(vendor["id"])
    payload["lines"][0]["purchase_order_line_id"] = po["lines"][0]["id"]
    assert_error(demo_api.post("/invoices", json=payload), 422, "validation_error", "lines[0].purchase_order_line_id")
    assert count(schema_session, Invoice) == count(schema_session, InvoiceLine) == 0


def test_foreign_details_counts_and_filters_are_hidden(demo_api, records, foreign_records):
    vendor, po = records
    foreign_vendor, foreign_po, foreign_receipt, foreign_invoice = foreign_records
    for resource, foreign, payload in [
        ("delivery-receipts", foreign_receipt, receipt_payload(po)),
        ("invoices", foreign_invoice, invoice_payload(vendor["id"], purchase_order_id=po["id"])),
    ]:
        assert_error(demo_api.get(f"/{resource}/{foreign.id}"), 404, "not_found")
        assert demo_api.get(f"/{resource}").json()["total"] == 0
        assert demo_api.post(f"/{resource}", json=payload).status_code == 201
        page = demo_api.get(f"/{resource}").json()
        assert page["total"] == len(page["items"]) == 1
        for order_id in (foreign_po.id, uuid4()):
            assert demo_api.get(f"/{resource}?purchase_order_id={order_id}").json()["total"] == 0
    assert demo_api.get(f"/invoices?supplier_id={foreign_vendor.id}").json()["total"] == 0
    assert demo_api.get(f"/invoices?supplier_id={uuid4()}").json()["total"] == 0


def test_duplicate_identifiers_database_conflicts_and_recovery(demo_api, records, schema_session):
    vendor, po = records
    for resource, payload, header, line_model, field in [
        ("delivery-receipts", receipt_payload(po), DeliveryReceipt, DeliveryReceiptLine, "receipt_number"),
        ("invoices", invoice_payload(vendor["id"]), Invoice, InvoiceLine, "invoice_number"),
    ]:
        assert demo_api.post(f"/{resource}", json=payload).status_code == 201
        duplicate = dict(payload)
        duplicate[field] = "  " + payload[field] + "  "
        assert_error(demo_api.post(f"/{resource}", json=duplicate), 409, "conflict", field)
        assert count(schema_session, header) == count(schema_session, line_model) == 1
        payload[field] = "RECOVERY"
        assert demo_api.post(f"/{resource}", json=payload).status_code == 201
        assert count(schema_session, header) == count(schema_session, line_model) == 2
    other = supplier(demo_api, "OTHER")
    assert demo_api.post("/invoices", json=invoice_payload(other["id"])).status_code == 201
    assert demo_api.post("/invoices", json=invoice_payload(vendor["id"], "inv-001")).status_code == 201


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
def test_bounded_pagination_stable_order_and_filters(demo_api, records, schema_session, resource):
    vendor, po = records
    other = supplier(demo_api, "OTHER")
    other_po = order(demo_api, other["id"], "OTHER")
    saved = []
    for index in range(3):
        selected = po if index < 2 else other_po
        payload = receipt_payload(selected, f"DR-{index}") if resource == "delivery-receipts" else invoice_payload(selected["supplier_id"], f"INV-{index}", purchase_order_id=selected["id"])
        response = demo_api.post(f"/{resource}", json=payload)
        assert response.status_code == 201, response.text
        saved.append(response.json())
    model = DeliveryReceipt if resource == "delivery-receipts" else Invoice
    schema_session.execute(update(model).values(created_at=datetime(2020, 1, 2, tzinfo=timezone.utc)))
    schema_session.execute(update(model).where(model.id == UUID(saved[0]["id"])).values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    expected = sorted([row["id"] for row in saved[1:]], reverse=True) + [saved[0]["id"]]
    page = demo_api.get(f"/{resource}?limit=2&offset=1").json()
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 1)
    assert [row["id"] for row in page["items"]] == expected[1:]
    assert all("lines" not in row for row in page["items"])
    assert demo_api.get(f"/{resource}?offset=10000").json()["items"] == []
    filtered = demo_api.get(f"/{resource}?purchase_order_id={po['id']}").json()
    assert filtered["total"] == 2
    assert all(row["purchase_order_id"] == po["id"] for row in filtered["items"])
    if resource == "invoices":
        assert demo_api.get(f"/invoices?supplier_id={vendor['id']}").json()["total"] == 2
        assert demo_api.get(f"/invoices?supplier_id={vendor['id']}&purchase_order_id={po['id']}").json()["total"] == 2
        assert demo_api.get(f"/invoices?supplier_id={other['id']}&purchase_order_id={po['id']}").json()["total"] == 0


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=1.5", "offset=-1", "offset=10001", "unknown=value", "workspace_id=value", "purchase_order_id=invalid"])
def test_invalid_list_parameters(demo_api, resource, query):
    assert_error(demo_api.get(f"/{resource}?{query}"), 422, "validation_error")


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
def test_malformed_uuid_and_missing_detail(demo_api, resource):
    assert_error(demo_api.get(f"/{resource}/invalid"), 422, "validation_error")
    assert_error(demo_api.get(f"/{resource}/{uuid4()}"), 404, "not_found")
    if resource == "invoices":
        assert_error(demo_api.get("/invoices?supplier_id=invalid"), 422, "validation_error")


def test_missing_workspace_does_not_initialize_on_new_routes(api_client, schema_session):
    po = {"id": str(uuid4()), "lines": [{"id": str(uuid4())}]}
    for resource, payload in [("delivery-receipts", receipt_payload(po)), ("invoices", invoice_payload(str(uuid4())))]:
        assert_error(api_client.post(f"/{resource}", json=payload), 403, "forbidden")
        assert_error(api_client.get(f"/{resource}"), 403, "forbidden")
        assert_error(api_client.get(f"/{resource}/{uuid4()}"), 403, "forbidden")
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 0
    assert api_client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("value", [8, 8.0, True, None, "", " 8", "8 ", "+8", "-8", "8e0", "NaN", "Infinity", "0", "0.000", "1.0000", "1000000000", "0" * 33 + "1", ".1", "1."])
def test_invalid_received_decimal_strings(demo_api, records, value):
    _, po = records
    payload = receipt_payload(po)
    payload["lines"][0]["quantity_received"] = value
    assert_error(demo_api.post("/delivery-receipts", json=payload), 422, "validation_error", "lines[0].quantity_received")


@pytest.mark.parametrize(("field", "value"), [
    ("quantity", 10), ("quantity", "+1"), ("quantity", "-1"), ("quantity", "1e1"), ("quantity", "NaN"), ("quantity", "Infinity"), ("quantity", " 1"), ("quantity", "0"), ("quantity", "1.0000"), ("quantity", "1000000000"),
    ("unit_price", 25), ("unit_price", "+1"), ("unit_price", "-1"), ("unit_price", "1e1"), ("unit_price", "NaN"), ("unit_price", "Infinity"), ("unit_price", "1 "), ("unit_price", "1.00000"), ("unit_price", "10000000000"),
    ("description", " "), ("description", "X" * 501), ("purchase_order_line_id", PRIVATE),
])
def test_invalid_invoice_lines(demo_api, records, field, value):
    vendor, _ = records
    payload = invoice_payload(vendor["id"])
    payload["lines"][0][field] = value
    assert_error(demo_api.post("/invoices", json=payload), 422, "validation_error", f"lines[0].{field}")


@pytest.mark.parametrize("value", [0, 0.0, True, None, "", " 0", "0 ", "+0", "-0", "1e1", "NaN", "Infinity", "0.000", "10000000000000000", "0" * 33, ".1", "1."])
def test_invalid_tax_strings(demo_api, records, value):
    vendor, _ = records
    assert_error(demo_api.post("/invoices", json=invoice_payload(vendor["id"], tax_amount=value)), 422, "validation_error", "tax_amount")


@pytest.mark.parametrize(("field", "value"), [
    ("invoice_number", " "), ("invoice_number", "X" * 65), ("invoice_date", "2026-02-30"),
    ("invoice_date", "2026-10-15T00:00:00Z"), ("invoice_date", "0000-01-01"),
    ("due_date", "2026-10-14"), ("due_date", "2026-02-30"), ("due_date", "2026-10-16T00:00:00Z"),
    ("currency", "USD"), ("notes", "X" * 2001), ("supplier_id", PRIVATE), ("purchase_order_id", PRIVATE),
    ("lines", []), ("lines", [{"description": "Keyboard", "quantity": "1", "unit_price": "1"}] * 101),
])
def test_invalid_invoice_fields(demo_api, records, field, value):
    vendor, _ = records
    payload = invoice_payload(vendor["id"])
    payload[field] = value
    assert_error(demo_api.post("/invoices", json=payload), 422, "validation_error", field)


def test_tax_amount_is_explicitly_required(demo_api, records):
    vendor, _ = records
    payload = invoice_payload(vendor["id"])
    del payload["tax_amount"]
    assert_error(demo_api.post("/invoices", json=payload), 422, "validation_error", "tax_amount")


@pytest.mark.parametrize(("field", "value"), [
    ("receipt_number", " "), ("receipt_number", "X" * 65), ("received_date", "2026-02-30"),
    ("received_date", "2026-10-14T00:00:00Z"), ("received_date", "0000-01-01"),
    ("purchase_order_id", PRIVATE), ("notes", "X" * 2001), ("lines", []),
])
def test_invalid_receipt_fields(demo_api, records, field, value):
    _, po = records
    assert_error(demo_api.post("/delivery-receipts", json=receipt_payload(po, **{field: value})), 422, "validation_error", field)


def test_receipt_line_count_limit(demo_api, records):
    _, po = records
    payload = receipt_payload(po)
    payload["lines"] *= 101
    assert_error(demo_api.post("/delivery-receipts", json=payload), 422, "validation_error", "lines")


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
@pytest.mark.parametrize("field", ["id", "workspace_id", "created_at", "status", "subtotal", "total", "unknown", PRIVATE])
def test_client_header_server_fields_rejected_without_echo(demo_api, records, resource, field):
    vendor, po = records
    payload = receipt_payload(po) if resource == "delivery-receipts" else invoice_payload(vendor["id"])
    payload[field] = PRIVATE
    assert_error(demo_api.post(f"/{resource}", json=payload), 422, "validation_error")


@pytest.mark.parametrize("status", ["draft", "approved"])
def test_even_valid_draft_status_cannot_be_client_supplied(demo_api, records, status):
    vendor, _ = records
    assert_error(demo_api.post("/invoices", json=invoice_payload(vendor["id"], status=status)), 422, "validation_error", "status")


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
@pytest.mark.parametrize("field", ["id", "workspace_id", "created_at", "line_no", "line_total", "purchase_order_id", "delivery_receipt_id", "invoice_id", "unknown", PRIVATE])
def test_client_line_server_fields_rejected_without_echo(demo_api, records, resource, field):
    vendor, po = records
    payload = receipt_payload(po) if resource == "delivery-receipts" else invoice_payload(vendor["id"])
    payload["lines"][0][field] = PRIVATE
    assert_error(demo_api.post(f"/{resource}", json=payload), 422, "validation_error")


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
def test_invalid_json_is_redacted(demo_api, resource):
    assert_error(demo_api.post(f"/{resource}", content='{"private":"' + PRIVATE + '", broken}', headers={"Content-Type": "application/json"}), 422, "validation_error")


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
def test_database_second_line_failure_rolls_back_and_recovers(demo_api, records, schema_session, resource):
    vendor, po = records
    header, line_model = (DeliveryReceipt, DeliveryReceiptLine) if resource == "delivery-receipts" else (Invoice, InvoiceLine)
    schema_session.execute(text("""
        CREATE FUNCTION pg_temp.reject_step34_line() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.line_no = 2 THEN
                RAISE EXCEPTION 'synthetic-private-value-that-must-not-appear-in-errors';
            END IF;
            RETURN NEW;
        END $$
    """))
    # The table name is one of the two constants above; all DDL is in the guarded
    # test's outer transaction and is removed by its rollback.
    schema_session.execute(text(f"CREATE TRIGGER reject_step34_line BEFORE INSERT ON {line_model.__tablename__} FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_step34_line()"))
    if resource == "delivery-receipts":
        po = order(demo_api, vendor["id"], "TWO", lines=[{"description": "Keyboard", "quantity": "10", "unit_price": "25"}] * 2)
        payload = receipt_payload(po, lines=[{"purchase_order_line_id": line["id"], "quantity_received": "1"} for line in po["lines"]])
        recovery = receipt_payload(po)
    else:
        payload = invoice_payload(vendor["id"], lines=[{"description": "Fictional line", "quantity": "1", "unit_price": "25"}] * 2)
        recovery = invoice_payload(vendor["id"])
    assert_error(demo_api.post(f"/{resource}", json=payload), 500, "internal_error")
    assert count(schema_session, header) == count(schema_session, line_model) == 0
    assert demo_api.post(f"/{resource}", json=recovery).status_code == 201


@pytest.mark.parametrize("resource", ["delivery-receipts", "invoices"])
def test_commit_failure_has_no_partial_save_or_success_and_recovers(demo_api, records, schema_session, resource):
    vendor, po = records
    header, line_model = (DeliveryReceipt, DeliveryReceiptLine) if resource == "delivery-receipts" else (Invoice, InvoiceLine)
    payload = receipt_payload(po) if resource == "delivery-receipts" else invoice_payload(vendor["id"])
    observed = []

    def fail_commit(session):
        observed.append((count(session, header), count(session, line_model)))
        raise OperationalError("INSERT INTO secret; postgresql://private", {"private": PRIVATE}, OSError(PRIVATE))

    event.listen(Session, "before_commit", fail_commit)
    try:
        response = demo_api.post(f"/{resource}", json=payload)
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert observed == [(1, 1)]
    assert_error(response, 503, "service_unavailable")
    assert count(schema_session, header) == count(schema_session, line_model) == 0
    assert demo_api.post(f"/{resource}", json=payload).status_code == 201


def test_api_commits_and_trigger_ddl_do_not_leak_between_tests(schema_session):
    for model in (Workspace, Supplier, PurchaseOrder, PurchaseOrderLine, DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine):
        assert schema_session.scalar(select(func.count()).select_from(model)) == 0
    assert schema_session.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgname = 'reject_step34_line'")) == 0
