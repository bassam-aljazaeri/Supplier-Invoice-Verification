"""Real PostgreSQL schema/ORM tests; synthetic data is rolled back per test."""

import os
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import insert, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, configure_mappers

from app import db
from app.models import (
    Base, Workspace, Supplier, PurchaseOrder, PurchaseOrderLine,
    DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine,
)
from scripts.check_schema import (
    TestTargetError, migration_config, prepare_test_database, require_test_marker,
)

pytestmark = pytest.mark.postgres
TABLES = {
    "workspaces", "suppliers", "purchase_orders", "purchase_order_lines",
    "delivery_receipts", "delivery_receipt_lines", "invoices", "invoice_lines",
}
DAY = date(2026, 10, 13)
PRICE_FIELDS = {"quantity": Decimal("10.000"), "unit_price": Decimal("25.0000"), "line_total": Decimal("250.00")}


@pytest.fixture
def graph(schema_session):
    session = schema_session
    wa = Workspace(slug="test-a", name="Synthetic workspace A")
    wb = Workspace(slug="test-b", name="Synthetic workspace B")
    session.add_all([wa, wb])
    session.flush()
    sa = Supplier(workspace_id=wa.id, supplier_code="DEMO-001", name="Synthetic supplier A")
    sb = Supplier(workspace_id=wa.id, supplier_code="DEMO-002", name="Synthetic supplier B")
    sc = Supplier(workspace_id=wb.id, supplier_code="DEMO-001", name="Synthetic supplier C")
    session.add_all([sa, sb, sc])
    session.flush()
    orders = [PurchaseOrder(
        workspace_id=workspace.id, supplier_id=supplier.id, po_number=number,
        order_date=DAY, currency="EUR", subtotal=Decimal("250.00"),
    ) for workspace, supplier, number in [
        (wa, sa, "PO-001"), (wa, sa, "PO-002"), (wa, sb, "PO-003"), (wb, sc, "PO-001"),
    ]]
    session.add_all(orders)
    session.flush()
    order_lines = [PurchaseOrderLine(
        workspace_id=order.workspace_id, purchase_order_id=order.id,
        line_no=1, description="Keyboard", **PRICE_FIELDS,
    ) for order in orders]
    session.add_all(order_lines)
    receipt = DeliveryReceipt(
        workspace_id=wa.id, purchase_order_id=orders[0].id,
        receipt_number="DR-001", received_date=DAY,
    )
    invoices = [Invoice(
        workspace_id=wa.id, supplier_id=sa.id, purchase_order_id=order_id,
        invoice_number=number, invoice_date=DAY, currency="EUR",
        subtotal=Decimal("250.00"), tax_amount=Decimal("0.00"), total=Decimal("250.00"),
    ) for order_id, number in [(orders[0].id, "INV-001"), (None, "INV-002")]]
    session.add_all([receipt, *invoices])
    session.flush()
    receipt_line = DeliveryReceiptLine(
        workspace_id=wa.id, delivery_receipt_id=receipt.id,
        purchase_order_id=orders[0].id, purchase_order_line_id=order_lines[0].id,
        line_no=1, quantity_received=Decimal("8.000"),
    )
    invoice_line = InvoiceLine(
        workspace_id=wa.id, invoice_id=invoices[0].id, line_no=1,
        description="Keyboard", purchase_order_id=orders[0].id,
        purchase_order_line_id=order_lines[0].id, **PRICE_FIELDS,
    )
    unmapped_line = InvoiceLine(
        workspace_id=wa.id, invoice_id=invoices[1].id, line_no=1,
        description="Keyboard", **PRICE_FIELDS,
    )
    session.add_all([receipt_line, invoice_line, unmapped_line])
    # Release the fixture savepoint so a later failed request's rollback keeps
    # the graph. The outer test transaction still rolls back every fixture row.
    session.commit()
    return dict(
        wa=wa, wb=wb, sa=sa, sb=sb, sc=sc,
        pa=orders[0], pb=orders[1], pc=orders[2], pd=orders[3],
        la=order_lines[0], lb=order_lines[1], lc=order_lines[2], ld=order_lines[3],
        receipt=receipt, receipt_line=receipt_line,
        invoice=invoices[0], no_order=invoices[1], invoice_line=invoice_line,
        unmapped_line=unmapped_line,
    )


def row_values(model, graph):
    g = graph
    if model is Supplier:
        return dict(workspace_id=g["wa"].id, supplier_code="NEW", name="Synthetic new supplier")
    if model is PurchaseOrder:
        return dict(workspace_id=g["wa"].id, supplier_id=g["sa"].id, po_number="NEW", order_date=DAY, currency="EUR", subtotal=Decimal("250.00"))
    if model is PurchaseOrderLine:
        return dict(workspace_id=g["wa"].id, purchase_order_id=g["pa"].id, line_no=2, description="Keyboard", **PRICE_FIELDS)
    if model is DeliveryReceipt:
        return dict(workspace_id=g["wa"].id, purchase_order_id=g["pa"].id, receipt_number="NEW", received_date=DAY)
    if model is DeliveryReceiptLine:
        return dict(workspace_id=g["wa"].id, delivery_receipt_id=g["receipt"].id, purchase_order_id=g["pa"].id, purchase_order_line_id=g["la"].id, line_no=2, quantity_received=Decimal("1.000"))
    if model is Invoice:
        return dict(workspace_id=g["wa"].id, supplier_id=g["sa"].id, invoice_number="NEW", invoice_date=DAY, currency="EUR", subtotal=Decimal("250.00"), tax_amount=Decimal("0.00"), total=Decimal("250.00"))
    if model is InvoiceLine:
        return dict(workspace_id=g["wa"].id, invoice_id=g["invoice"].id, line_no=2, description="Keyboard", **PRICE_FIELDS)
    raise AssertionError("Unknown fixture model")


def test_schema_matches_reviewed_metadata_and_named_constraints(postgres_engine):
    with postgres_engine.connect() as connection:
        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == TABLES | {"alembic_version"}
        assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True}), Base.metadata) == []
        for table_name, table in Base.metadata.tables.items():
            columns = {column["name"]: column for column in inspector.get_columns(table_name)}
            assert str(columns["id"]["type"]) == "UUID"
            assert columns["id"]["nullable"] is False
            assert "gen_random_uuid" in columns["id"]["default"]
            assert columns["created_at"]["type"].timezone is True
            assert columns["created_at"]["nullable"] is False
            assert columns["created_at"]["default"] is not None
            actual_names = {inspector.get_pk_constraint(table_name)["name"]}
            for loader in (inspector.get_foreign_keys, inspector.get_unique_constraints, inspector.get_check_constraints):
                actual_names.update(item["name"] for item in loader(table_name))
            assert all(constraint.name for constraint in table.constraints)
            assert {constraint.name for constraint in table.constraints} == actual_names
            actual_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
            assert {index.name for index in table.indexes} <= actual_indexes
            for foreign_key in inspector.get_foreign_keys(table_name):
                assert foreign_key["options"]["ondelete"] == "RESTRICT"
            for column in table.columns:
                assert columns[column.name]["nullable"] == column.nullable
                if hasattr(column.type, "scale"):
                    assert columns[column.name]["type"].precision == column.type.precision
                    assert columns[column.name]["type"].scale == column.type.scale
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_manual_records"


def test_migration_upgrade_is_repeatable_and_downgrade_round_trips(postgres_engine):
    # Destructive lifecycle checks get an additional connected guard immediately
    # before downgrade and run only on the disposable database, with no fixture rows.
    with postgres_engine.connect() as connection:
        require_test_marker(connection, os.environ)
        assert connection.execute(select(Workspace)).first() is None
    config = migration_config()
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    try:
        command.downgrade(config, "base")
        with postgres_engine.connect() as connection:
            assert set(inspect(connection).get_table_names()) == {"alembic_version"}
            assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
    finally:
        command.upgrade(config, "head")
    with postgres_engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == TABLES | {"alembic_version"}
        assert connection.execute(select(Workspace)).first() is None


def test_direct_database_defaults_without_python_defaults(schema_session, graph):
    table = Workspace.__table__
    row = schema_session.execute(insert(table).values(slug="direct", name="Synthetic direct insert").returning(table.c.id, table.c.created_at)).one()
    assert isinstance(row.id, UUID)
    assert row.created_at.tzinfo is not None
    table = Invoice.__table__
    row = schema_session.execute(insert(table).values(**row_values(Invoice, graph)).returning(table.c.id, table.c.created_at, table.c.status)).one()
    assert isinstance(row.id, UUID)
    assert row.created_at.tzinfo is not None
    assert row.status == "draft"


def test_models_load_all_reviewed_relationships_without_mapper_warnings(schema_session, graph):
    configure_mappers()
    schema_session.expire_all()
    g = graph
    assert g["sa"].workspace is g["wa"]
    assert g["sa"] in g["wa"].suppliers
    assert g["pa"] in g["wa"].purchase_orders
    assert g["receipt"] in g["wa"].delivery_receipts
    assert g["invoice"] in g["wa"].invoices
    assert g["pa"].supplier is g["sa"]
    assert g["pa"] in g["sa"].purchase_orders
    assert g["invoice"] in g["sa"].invoices
    assert g["pa"].lines == [g["la"]]
    assert g["la"].purchase_order is g["pa"]
    assert g["receipt"].purchase_order is g["pa"]
    assert g["receipt"] in g["pa"].delivery_receipts
    assert g["receipt"].lines == [g["receipt_line"]]
    assert g["receipt_line"].delivery_receipt is g["receipt"]
    assert g["receipt_line"].purchase_order_line is g["la"]
    assert g["invoice"].supplier is g["sa"]
    assert g["invoice"].purchase_order is g["pa"]
    assert g["invoice"] in g["pa"].invoices
    assert g["invoice"].lines == [g["invoice_line"]]
    assert g["invoice_line"].invoice is g["invoice"]
    assert g["invoice_line"].purchase_order_line is g["la"]
    assert g["no_order"].purchase_order is None
    assert g["unmapped_line"].purchase_order_line is None
    for key in ("pa", "la", "receipt", "receipt_line", "invoice", "invoice_line"):
        assert g[key].workspace is g["wa"]
    assert g["receipt_line"].quantity_received == Decimal("8.000")
    assert g["invoice_line"].quantity == Decimal("10.000")


def test_writable_parent_relationships_do_not_overwrite_workspace(schema_session, graph):
    g = graph
    order = PurchaseOrder(
        workspace_id=g["wa"].id, supplier=g["sa"], po_number="RELATION", order_date=DAY,
        currency="EUR", subtotal=Decimal("250.00"),
        lines=[PurchaseOrderLine(workspace_id=g["wa"].id, line_no=1, description="Keyboard", **PRICE_FIELDS)],
    )
    schema_session.add(order)
    schema_session.flush()
    assert order.supplier_id == g["sa"].id
    assert order.lines[0].purchase_order_id == order.id
    receipt = DeliveryReceipt(
        workspace_id=g["wa"].id, purchase_order=order, receipt_number="RELATION", received_date=DAY,
        lines=[DeliveryReceiptLine(workspace_id=g["wa"].id, purchase_order_line_id=order.lines[0].id, line_no=1, quantity_received=Decimal("8"))],
    )
    invoice = Invoice(
        workspace_id=g["wa"].id, supplier=g["sa"], purchase_order=order,
        invoice_number="RELATION", invoice_date=DAY, currency="EUR",
        subtotal=Decimal("250"), tax_amount=Decimal("0"), total=Decimal("250"),
        lines=[InvoiceLine(workspace_id=g["wa"].id, line_no=1, description="Keyboard", **PRICE_FIELDS)],
    )
    schema_session.add_all([receipt, invoice])
    schema_session.flush()
    assert receipt.lines[0].purchase_order_id == order.id
    assert receipt.lines[0].delivery_receipt_id == receipt.id
    assert invoice.lines[0].invoice_id == invoice.id
    assert invoice.lines[0].purchase_order_id is None
    assert invoice.workspace_id == receipt.workspace_id == order.workspace_id == g["wa"].id


@pytest.mark.parametrize(("model", "overrides"), [
    (Supplier, {"workspace_id": "missing"}),
    (PurchaseOrder, {"supplier_id": "sc"}),
    (PurchaseOrderLine, {"workspace_id": "wb"}),
    (DeliveryReceipt, {"workspace_id": "wb"}),
    (DeliveryReceiptLine, {"workspace_id": "wb"}),
    (Invoice, {"supplier_id": "sc"}),
    (Invoice, {"purchase_order_id": "pd"}),
    (InvoiceLine, {"workspace_id": "wb"}),
    (Invoice, {"purchase_order_id": "pc"}),
    (DeliveryReceiptLine, {"purchase_order_line_id": "lb"}),
    (DeliveryReceiptLine, {"purchase_order_id": "pb", "purchase_order_line_id": "lb"}),
    (InvoiceLine, {"purchase_order_id": "pa", "purchase_order_line_id": "lb"}),
    (InvoiceLine, {"purchase_order_id": "pb", "purchase_order_line_id": "lb"}),
    (InvoiceLine, {"invoice_id": "no_order", "purchase_order_id": "pa", "purchase_order_line_id": "la"}),
])
def test_cross_workspace_and_incompatible_links_rejected(schema_session, graph, model, overrides):
    values = row_values(model, graph)
    values.update({key: uuid4() if value == "missing" else graph[value].id for key, value in overrides.items()})
    with pytest.raises(IntegrityError) as error:
        schema_session.add(model(**values))
        schema_session.flush()
    assert error.value.orig.sqlstate == "23503"
    schema_session.rollback()
    assert schema_session.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.parametrize(("order_key", "line_key"), [("pa", None), (None, "la")])
def test_incomplete_nullable_mapping_pairs_rejected(schema_session, graph, order_key, line_key):
    values = row_values(InvoiceLine, graph)
    values.update(purchase_order_id=graph[order_key].id if order_key else None, purchase_order_line_id=graph[line_key].id if line_key else None)
    with pytest.raises(IntegrityError) as error:
        schema_session.add(InvoiceLine(**values))
        schema_session.flush()
    assert error.value.orig.diag.constraint_name == "ck_invoice_lines_mapping_pair"
    schema_session.rollback()


def test_unmapped_lines_allowed_even_with_selected_order(schema_session, graph):
    line = InvoiceLine(**row_values(InvoiceLine, graph))
    schema_session.add(line)
    schema_session.flush()
    assert line.purchase_order_id is None
    assert line.purchase_order_line_id is None


@pytest.mark.parametrize(("model", "overrides"), [
    (Supplier, {"supplier_code": "DEMO-001"}),
    (PurchaseOrder, {"po_number": "PO-001"}),
    (DeliveryReceipt, {"receipt_number": "DR-001"}),
    (Invoice, {"invoice_number": "INV-001"}),
    (PurchaseOrderLine, {"line_no": 1}),
    (DeliveryReceiptLine, {}),
    (InvoiceLine, {"line_no": 1}),
])
def test_scoped_identifiers_and_line_uniqueness(schema_session, graph, model, overrides):
    values = row_values(model, graph)
    values.update(overrides)
    with pytest.raises(IntegrityError) as error:
        schema_session.add(model(**values))
        schema_session.flush()
    assert error.value.orig.sqlstate == "23505"
    schema_session.rollback()


def test_identifier_case_and_supplier_scope_allow_distinct_records(schema_session, graph):
    schema_session.add(Supplier(workspace_id=graph["wa"].id, supplier_code="demo-001", name="Synthetic distinct case"))
    values = row_values(Invoice, graph)
    values.update(supplier_id=graph["sb"].id, invoice_number="INV-001")
    schema_session.add(Invoice(**values))
    schema_session.flush()


@pytest.mark.parametrize(("key", "field", "value", "sqlstate"), [
    ("la", "quantity", Decimal("0"), "23514"),
    ("la", "quantity", Decimal("-1"), "23514"),
    ("la", "quantity", Decimal("NaN"), "23514"),
    ("la", "quantity", Decimal("1000000000"), "22003"),
    ("la", "unit_price", Decimal("-0.01"), "23514"),
    ("la", "unit_price", Decimal("NaN"), "23514"),
    ("la", "unit_price", Decimal("10000000000"), "22003"),
    ("la", "line_total", Decimal("-1"), "23514"),
    ("la", "line_total", Decimal("NaN"), "23514"),
    ("la", "line_total", Decimal("10000000000000000"), "22003"),
    ("la", "line_no", 0, "23514"),
    ("la", "description", " \t\n", "23514"),
    ("receipt_line", "quantity_received", Decimal("0"), "23514"),
    ("receipt_line", "quantity_received", Decimal("NaN"), "23514"),
    ("receipt_line", "quantity_received", Decimal("1000000000"), "22003"),
    ("invoice_line", "quantity", Decimal("0"), "23514"),
    ("invoice_line", "unit_price", Decimal("-1"), "23514"),
    ("invoice_line", "line_total", Decimal("-1"), "23514"),
    ("pa", "currency", "USD", "23514"),
    ("pa", "order_date", "2026-02-30", "22008"),
    ("pa", "order_date", "infinity", "23514"),
    ("pa", "subtotal", Decimal("-1"), "23514"),
    ("pa", "po_number", " ", "23514"),
    ("pa", "po_number", " PO-001 ", "23514"),
    ("receipt", "received_date", "2026-02-30", "22008"),
    ("receipt", "received_date", "infinity", "23514"),
    ("receipt", "receipt_number", "", "23514"),
    ("invoice", "currency", "GBP", "23514"),
    ("invoice", "status", "approved", "23514"),
    ("invoice", "invoice_date", "2026-02-30", "22008"),
    ("invoice", "due_date", date(2026, 10, 12), "23514"),
    ("invoice", "due_date", "infinity", "23514"),
    ("invoice", "subtotal", Decimal("-1"), "23514"),
    ("invoice", "tax_amount", Decimal("-1"), "23514"),
    ("invoice", "total", Decimal("249"), "23514"),
    ("invoice", "total", Decimal("NaN"), "23514"),
    ("invoice", "invoice_number", "", "23514"),
    ("sa", "supplier_code", "\tDEMO-001", "23514"),
    ("sa", "name", "", "23514"),
    ("sa", "name", "X" * 201, "22001"),
    ("sa", "name", None, "23502"),
    ("wa", "slug", "", "23514"),
])
def test_invalid_values_rejected_by_postgresql(schema_session, graph, key, field, value, sqlstate):
    record = graph[key]
    with pytest.raises(DBAPIError) as error:
        schema_session.execute(update(type(record)).where(type(record).id == record.id).values({field: value}))
    assert error.value.orig.sqlstate == sqlstate
    schema_session.rollback()
    assert schema_session.execute(text("SELECT 1")).scalar_one() == 1


def test_fractional_quantity_zero_price_and_upper_bound_are_exact(schema_session, graph):
    line = PurchaseOrderLine(**(row_values(PurchaseOrderLine, graph) | {
        "quantity": Decimal("0.001"), "unit_price": Decimal("0.0000"), "line_total": Decimal("0.00"),
    }))
    schema_session.add(line)
    schema_session.flush()
    schema_session.refresh(line)
    assert line.quantity == Decimal("0.001")
    assert line.unit_price == Decimal("0.0000")
    assert isinstance(line.line_total, Decimal)
    schema_session.execute(update(PurchaseOrderLine).where(PurchaseOrderLine.id == line.id).values(quantity=Decimal("999999999.999"), unit_price=Decimal("9999999999.9999")))
    schema_session.refresh(line)
    assert line.quantity == Decimal("999999999.999")
    assert line.unit_price == Decimal("9999999999.9999")


def test_later_line_failure_rolls_back_header_and_earlier_line(schema_session, graph):
    order = PurchaseOrder(**row_values(PurchaseOrder, graph))
    schema_session.add(order)
    schema_session.flush()
    order_id = order.id
    line = PurchaseOrderLine(workspace_id=graph["wa"].id, purchase_order_id=order.id, line_no=1, description="Keyboard", **PRICE_FIELDS)
    schema_session.add(line)
    schema_session.flush()
    line_id = line.id
    with pytest.raises(IntegrityError):
        schema_session.add(PurchaseOrderLine(workspace_id=graph["wa"].id, purchase_order_id=order.id, line_no=2, description="Invalid later line", **(PRICE_FIELDS | {"quantity": Decimal("0")})))
        schema_session.flush()
    schema_session.rollback()
    assert schema_session.get(PurchaseOrder, order_id) is None
    assert schema_session.get(PurchaseOrderLine, line_id) is None
    schema_session.add(Supplier(**row_values(Supplier, graph)))
    schema_session.commit()
    assert schema_session.scalar(select(Supplier).where(Supplier.supplier_code == "NEW")) is not None


@pytest.mark.parametrize("commit", [False, True])
def test_real_request_session_requires_explicit_commit(schema_session, monkeypatch, commit):
    connection = schema_session.connection()
    monkeypatch.setattr(db, "SessionLocal", lambda: Session(bind=connection, join_transaction_mode="create_savepoint"))
    dependency = db.get_session()
    session = next(dependency)
    workspace = Workspace(slug="request-test", name="Synthetic request workspace")
    session.add(workspace)
    session.flush()
    workspace_id = workspace.id
    if commit:
        session.commit()
    with pytest.raises(StopIteration):
        next(dependency)
    assert (schema_session.get(Workspace, workspace_id) is not None) is commit


def test_marker_cannot_relabel_populated_database_or_another_project(schema_session, graph):
    settings = dict(os.environ)
    settings["POSTGRES_TEST_PROJECT"] = "supplier-invoice-verification-check-" + "b" * 32
    with pytest.raises(TestTargetError, match="Refusing to mark"):
        prepare_test_database(schema_session.connection(), settings)
