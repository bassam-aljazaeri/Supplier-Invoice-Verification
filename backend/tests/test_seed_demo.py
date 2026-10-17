"""Whole-fixture repeatability/conflict proofs on guarded disposable PostgreSQL."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import seed_demo
from app.models import ApplicationUser, Base, DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine, PurchaseOrder, PurchaseOrderLine, Supplier, Workspace, WorkspaceMembership
from app.schemas.delivery_receipt import DeliveryReceiptCreate
from app.schemas.invoice import InvoiceCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.supplier import SupplierCreate
from app.seed_demo import (
    DEMO_INVOICE_ID, DEMO_INVOICE_LINE_ID, DEMO_ORDER_ID, DEMO_ORDER_LINE_ID,
    DEMO_RECEIPT_ID, DEMO_RECEIPT_LINE_ID, DEMO_SUPPLIER_ID, SeedConflict,
    ensure_demo_records, initialize_demo,
)
from app.services import manual_records as services
from app.workspace import DEMO_WORKSPACE_ID

pytestmark = pytest.mark.postgres
PRIVATE = "synthetic-private-conflict-value"


def snapshot(session):
    # This fixture owns the original eight business/workspace tables. Explicit
    # assertions below check that it grants no identities or memberships.
    return {table.name: session.execute(select(table).order_by(table.c.id)).all() for table in Base.metadata.sorted_tables if table.name not in {"application_users", "workspace_memberships"}}


def supplier_input(code="DEMO-OFFICE-001"):
    return SupplierCreate.model_validate({"supplier_code": code, "name": "Demo Office Supplies", "notes": "Fictional supplier for the local demonstration."})


def order_input(supplier_id=DEMO_SUPPLIER_ID, number="PO-DEMO-001"):
    return PurchaseOrderCreate.model_validate({"supplier_id": str(supplier_id), "po_number": number, "order_date": "2026-10-13", "currency": "EUR", "lines": [{"description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000"}]})


def receipt_input(order_id=DEMO_ORDER_ID, line_id=DEMO_ORDER_LINE_ID, number="DR-DEMO-001"):
    return DeliveryReceiptCreate.model_validate({"purchase_order_id": str(order_id), "receipt_number": number, "received_date": "2026-10-14", "lines": [{"purchase_order_line_id": str(line_id), "quantity_received": "8.000"}]})


def invoice_input(supplier_id=DEMO_SUPPLIER_ID, order_id=DEMO_ORDER_ID, line_id=DEMO_ORDER_LINE_ID, number="INV-DEMO-001"):
    return InvoiceCreate.model_validate({"supplier_id": str(supplier_id), "purchase_order_id": str(order_id), "invoice_number": number, "invoice_date": "2026-10-15", "due_date": "2026-11-14", "currency": "EUR", "tax_amount": "0.00", "lines": [{"description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000", "purchase_order_line_id": str(line_id)}]})


def test_fresh_seed_links_exact_fixture_with_one_commit(schema_session, api_client, grant_demo_access):
    commits = []
    event.listen(schema_session, "before_commit", lambda session: commits.append(snapshot(session)))
    initialize_demo(schema_session)
    assert len(commits) == 1
    assert all(len(rows) == 1 for rows in snapshot(schema_session).values())
    for model in (ApplicationUser, WorkspaceMembership):
        assert schema_session.scalar(select(func.count()).select_from(model)) == 0
    assert str(DEMO_SUPPLIER_ID) == "10000000-0000-4000-8000-000000000001"
    assert str(DEMO_ORDER_ID) == "20000000-0000-4000-8000-000000000001"
    assert str(DEMO_RECEIPT_ID) == "30000000-0000-4000-8000-000000000001"
    assert str(DEMO_INVOICE_ID) == "40000000-0000-4000-8000-000000000001"
    po = schema_session.get(PurchaseOrder, DEMO_ORDER_ID)
    receipt = schema_session.get(DeliveryReceipt, DEMO_RECEIPT_ID)
    invoice = schema_session.get(Invoice, DEMO_INVOICE_ID)
    assert po.lines[0].id == DEMO_ORDER_LINE_ID
    assert po.lines[0].quantity == Decimal("10.000")
    assert po.lines[0].unit_price == Decimal("25.0000")
    assert po.lines[0].line_total == po.subtotal == Decimal("250.00")
    assert receipt.lines[0].id == DEMO_RECEIPT_LINE_ID
    assert receipt.lines[0].quantity_received == Decimal("8.000")
    assert receipt.lines[0].purchase_order_line.id == DEMO_ORDER_LINE_ID
    assert invoice.lines[0].id == DEMO_INVOICE_LINE_ID
    assert invoice.lines[0].quantity == Decimal("10.000")
    assert invoice.lines[0].purchase_order_line.id == DEMO_ORDER_LINE_ID
    assert invoice.subtotal == invoice.total == Decimal("250.00")
    assert invoice.tax_amount == Decimal("0.00") and invoice.status == "draft"
    assert invoice.due_date == date(2026, 11, 14)
    grant_demo_access()
    for resource, record_id in [("suppliers", DEMO_SUPPLIER_ID), ("purchase-orders", DEMO_ORDER_ID), ("delivery-receipts", DEMO_RECEIPT_ID), ("invoices", DEMO_INVOICE_ID)]:
        result = api_client.get(f"/{resource}/{record_id}")
        assert result.status_code == 200
        assert result.json()["id"] == str(record_id)
    assert api_client.get(f"/invoices/{DEMO_INVOICE_ID}").json()["total"] == "250.00"


def test_repeat_seed_keeps_every_id_value_line_count_and_timestamp(schema_session):
    initialize_demo(schema_session)
    # Old timestamps distinguish preservation from any CURRENT_TIMESTAMP update
    # within this fixture's outer transaction.
    for table in Base.metadata.sorted_tables:
        schema_session.execute(update(table).values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    schema_session.commit()
    before = snapshot(schema_session)
    initialize_demo(schema_session)
    assert snapshot(schema_session) == before


def test_reusable_whole_seed_helper_never_commits(schema_session):
    ensure_demo_records(schema_session)
    assert all(len(rows) == 1 for rows in snapshot(schema_session).values())
    schema_session.rollback()
    assert all(not rows for rows in snapshot(schema_session).values())


@pytest.mark.parametrize("missing", ["supplier_only", "invoice_line", "receipt_line"])
def test_missing_expected_records_are_inserted_without_changing_existing_rows(schema_session, missing):
    if missing == "supplier_only":
        from app.seed_workspace import ensure_demo_workspace
        ensure_demo_workspace(schema_session)
        supplier = services.build_supplier(DEMO_WORKSPACE_ID, supplier_input())
        supplier.id = DEMO_SUPPLIER_ID
        schema_session.add(supplier)
    else:
        initialize_demo(schema_session)
        model, record_id = (InvoiceLine, DEMO_INVOICE_LINE_ID) if missing == "invoice_line" else (DeliveryReceiptLine, DEMO_RECEIPT_LINE_ID)
        schema_session.execute(delete(model).where(model.id == record_id))
    schema_session.commit()
    before = snapshot(schema_session)
    initialize_demo(schema_session)
    after = snapshot(schema_session)
    for table, rows in before.items():
        assert all(row in after[table] for row in rows)
    assert all(len(rows) == 1 for rows in after.values())


def test_missing_order_line_in_existing_header_is_repaired(schema_session):
    from app.seed_workspace import ensure_demo_workspace
    ensure_demo_workspace(schema_session)
    vendor = services.build_supplier(DEMO_WORKSPACE_ID, supplier_input())
    vendor.id = DEMO_SUPPLIER_ID
    schema_session.add(vendor)
    schema_session.flush()
    built = services.build_purchase_order(schema_session, DEMO_WORKSPACE_ID, order_input())
    # A header without lines is a possible partial direct database fixture.
    partial = PurchaseOrder(id=DEMO_ORDER_ID, workspace_id=DEMO_WORKSPACE_ID, supplier_id=DEMO_SUPPLIER_ID, po_number=built.po_number, order_date=built.order_date, currency=built.currency, subtotal=built.subtotal)
    schema_session.add(partial)
    schema_session.commit()
    assert partial.lines == []
    initialize_demo(schema_session)
    assert schema_session.get(PurchaseOrder, DEMO_ORDER_ID).lines[0].id == DEMO_ORDER_LINE_ID
    assert all(len(rows) == 1 for rows in snapshot(schema_session).values())


@pytest.mark.parametrize(("model", "record_id", "changes"), [
    (Supplier, DEMO_SUPPLIER_ID, {"name": PRIVATE}),
    (Supplier, DEMO_SUPPLIER_ID, {"notes": PRIVATE}),
    (PurchaseOrder, DEMO_ORDER_ID, {"order_date": date(2026, 10, 12)}),
    (PurchaseOrder, DEMO_ORDER_ID, {"notes": PRIVATE}),
    (PurchaseOrderLine, DEMO_ORDER_LINE_ID, {"quantity": Decimal("9")}),
    (PurchaseOrderLine, DEMO_ORDER_LINE_ID, {"unit_price": Decimal("26")}),
    (DeliveryReceiptLine, DEMO_RECEIPT_LINE_ID, {"quantity_received": Decimal("9")}),
    (DeliveryReceiptLine, DEMO_RECEIPT_LINE_ID, {"line_no": 2}),
    (Invoice, DEMO_INVOICE_ID, {"tax_amount": Decimal("1"), "total": Decimal("251")}),
    (Invoice, DEMO_INVOICE_ID, {"due_date": date(2026, 11, 15)}),
    (InvoiceLine, DEMO_INVOICE_LINE_ID, {"description": PRIVATE}),
    (InvoiceLine, DEMO_INVOICE_LINE_ID, {"purchase_order_id": None, "purchase_order_line_id": None}),
])
def test_existing_fixture_values_conflict_without_overwrite(schema_session, model, record_id, changes):
    initialize_demo(schema_session)
    schema_session.execute(update(model).where(model.id == record_id).values(**changes))
    schema_session.commit()
    before = snapshot(schema_session)
    with pytest.raises(SeedConflict, match="nothing was overwritten") as failure:
        initialize_demo(schema_session)
    assert PRIVATE not in str(failure.value)
    assert snapshot(schema_session) == before


@pytest.mark.parametrize("kind", ["supplier", "order", "receipt", "invoice"])
def test_scoped_natural_key_with_another_id_conflicts(schema_session, kind):
    initialize_demo(schema_session)
    deletion_order = [(InvoiceLine, DEMO_INVOICE_LINE_ID), (Invoice, DEMO_INVOICE_ID), (DeliveryReceiptLine, DEMO_RECEIPT_LINE_ID), (DeliveryReceipt, DEMO_RECEIPT_ID), (PurchaseOrderLine, DEMO_ORDER_LINE_ID), (PurchaseOrder, DEMO_ORDER_ID), (Supplier, DEMO_SUPPLIER_ID)]
    stop = {"supplier": Supplier, "order": PurchaseOrder, "receipt": DeliveryReceipt, "invoice": Invoice}[kind]
    for model, record_id in deletion_order:
        schema_session.execute(delete(model).where(model.id == record_id))
        if model is stop:
            break
    schema_session.commit()
    if kind == "supplier":
        services.create_supplier(schema_session, DEMO_WORKSPACE_ID, supplier_input())
    elif kind == "order":
        services.create_purchase_order(schema_session, DEMO_WORKSPACE_ID, order_input())
    elif kind == "receipt":
        services.create_delivery_receipt(schema_session, DEMO_WORKSPACE_ID, receipt_input())
    else:
        services.create_invoice(schema_session, DEMO_WORKSPACE_ID, invoice_input())
    before = snapshot(schema_session)
    with pytest.raises(SeedConflict):
        initialize_demo(schema_session)
    assert snapshot(schema_session) == before


def foreign_workflow(session, collision=None, prefix="MANUAL", workspace_id=None):
    if workspace_id is None:
        workspace = Workspace(slug="foreign-demo", name="Fictional other workspace")
        session.add(workspace)
        session.flush()
        workspace_id = workspace.id
    fixed = {Supplier: DEMO_SUPPLIER_ID, PurchaseOrder: DEMO_ORDER_ID, PurchaseOrderLine: DEMO_ORDER_LINE_ID, DeliveryReceipt: DEMO_RECEIPT_ID, DeliveryReceiptLine: DEMO_RECEIPT_LINE_ID, Invoice: DEMO_INVOICE_ID, InvoiceLine: DEMO_INVOICE_LINE_ID}
    vendor = services.build_supplier(workspace_id, supplier_input(prefix + "-SUPPLIER"))
    vendor.id = fixed[Supplier] if collision is Supplier else uuid4()
    session.add(vendor)
    session.flush()
    order = services.build_purchase_order(session, workspace_id, order_input(vendor.id, prefix + "-ORDER"))
    order.id = fixed[PurchaseOrder] if collision is PurchaseOrder else uuid4()
    order.lines[0].id = fixed[PurchaseOrderLine] if collision is PurchaseOrderLine else uuid4()
    session.add(order)
    session.flush()
    receipt = services.build_delivery_receipt(session, workspace_id, receipt_input(order.id, order.lines[0].id, prefix + "-RECEIPT"))
    receipt.id = fixed[DeliveryReceipt] if collision is DeliveryReceipt else uuid4()
    receipt.lines[0].id = fixed[DeliveryReceiptLine] if collision is DeliveryReceiptLine else uuid4()
    session.add(receipt)
    session.flush()
    invoice = services.build_invoice(session, workspace_id, invoice_input(vendor.id, order.id, order.lines[0].id, prefix + "-INVOICE"))
    invoice.id = fixed[Invoice] if collision is Invoice else uuid4()
    invoice.lines[0].id = fixed[InvoiceLine] if collision is InvoiceLine else uuid4()
    session.add(invoice)
    session.commit()
    return vendor, order, receipt, invoice


@pytest.mark.parametrize("collision", [Supplier, PurchaseOrder, PurchaseOrderLine, DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine])
def test_global_fixed_id_collision_rolls_back_all_new_fixture_rows(schema_session, collision):
    foreign_workflow(schema_session, collision)
    before = snapshot(schema_session)
    with pytest.raises(SeedConflict):
        initialize_demo(schema_session)
    assert snapshot(schema_session) == before
    assert schema_session.get(Workspace, DEMO_WORKSPACE_ID) is None


def test_unrelated_manual_ui_and_other_scoped_identifiers_are_preserved(schema_session):
    from app.seed_workspace import ensure_demo_workspace
    ensure_demo_workspace(schema_session)
    foreign_workflow(schema_session, prefix="MANUAL", workspace_id=DEMO_WORKSPACE_ID)
    ui_vendor, _, _, _ = foreign_workflow(schema_session, prefix="UI", workspace_id=DEMO_WORKSPACE_ID)
    # Invoice numbers are supplier-scoped; the same demo number on another
    # supplier must not be adopted, rejected, or changed by this seeder.
    services.create_invoice(schema_session, DEMO_WORKSPACE_ID, invoice_input(ui_vendor.id, schema_session.scalar(select(PurchaseOrder.id).where(PurchaseOrder.supplier_id == ui_vendor.id)), schema_session.scalar(select(PurchaseOrderLine.id).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id).where(PurchaseOrder.supplier_id == ui_vendor.id)), "INV-DEMO-001"))
    other = Workspace(slug="same-keys-elsewhere", name="Fictional isolated workspace")
    schema_session.add(other)
    schema_session.flush()
    services.create_supplier(schema_session, other.id, supplier_input())
    before = snapshot(schema_session)
    initialize_demo(schema_session)
    first = snapshot(schema_session)
    for table, rows in before.items():
        assert all(row in first[table] for row in rows)
    initialize_demo(schema_session)
    assert snapshot(schema_session) == first


@pytest.mark.parametrize("model", [PurchaseOrderLine, InvoiceLine])
def test_unexpected_extra_demo_lines_conflict(schema_session, model):
    initialize_demo(schema_session)
    values = {"workspace_id": DEMO_WORKSPACE_ID, "line_no": 2, "description": "Fictional extra line", "quantity": Decimal("1"), "unit_price": Decimal("0"), "line_total": Decimal("0")}
    values["purchase_order_id" if model is PurchaseOrderLine else "invoice_id"] = DEMO_ORDER_ID if model is PurchaseOrderLine else DEMO_INVOICE_ID
    schema_session.add(model(**values))
    schema_session.commit()
    before = snapshot(schema_session)
    with pytest.raises(SeedConflict, match="unexpected lines"):
        initialize_demo(schema_session)
    assert snapshot(schema_session) == before


def test_late_line_database_failure_rolls_back_workspace_and_all_documents(schema_session):
    schema_session.execute(text("""
        CREATE FUNCTION pg_temp.reject_demo_line() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'synthetic-private-conflict-value'; END $$
    """))
    schema_session.execute(text("CREATE TRIGGER reject_demo_line BEFORE INSERT ON invoice_lines FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_demo_line()"))
    schema_session.commit()
    with pytest.raises(SQLAlchemyError):
        initialize_demo(schema_session)
    assert all(not rows for rows in snapshot(schema_session).values())
    schema_session.execute(text("DROP TRIGGER reject_demo_line ON invoice_lines"))
    schema_session.commit()
    initialize_demo(schema_session)
    assert all(len(rows) == 1 for rows in snapshot(schema_session).values())


def test_commit_failure_rolls_back_entire_seed_and_next_seed_succeeds(schema_session):
    seen = []
    def fail_commit(session):
        seen.append(all(len(rows) == 1 for rows in snapshot(session).values()))
        raise OperationalError("private SQL", {}, OSError(PRIVATE))
    event.listen(schema_session, "before_commit", fail_commit)
    try:
        with pytest.raises(OperationalError):
            initialize_demo(schema_session)
    finally:
        event.remove(schema_session, "before_commit", fail_commit)
    assert seen == [True]
    assert all(not rows for rows in snapshot(schema_session).values())
    initialize_demo(schema_session)
    assert all(len(rows) == 1 for rows in snapshot(schema_session).values())


def test_explicit_cli_twice_and_sanitized_conflict_exit(schema_session, monkeypatch, capsys):
    connection = schema_session.connection()
    monkeypatch.setattr(seed_demo, "SessionLocal", lambda: Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False))
    assert seed_demo.main() == seed_demo.main() == 0
    schema_session.execute(update(Supplier).where(Supplier.id == DEMO_SUPPLIER_ID).values(name=PRIVATE))
    schema_session.commit()
    before = snapshot(schema_session)
    assert seed_demo.main() == 1
    output = capsys.readouterr()
    assert "nothing was overwritten" in output.err and PRIVATE not in output.err
    assert snapshot(schema_session) == before


def test_seed_does_not_leak_to_later_tests(schema_session):
    assert all(not rows for rows in snapshot(schema_session).values())
