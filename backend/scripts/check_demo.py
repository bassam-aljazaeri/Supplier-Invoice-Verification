"""Seed and verify the fictional workflow only in a guarded disposable stack."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.db import create_database_engine
from app.schemas.delivery_receipt import DeliveryReceiptRead
from app.schemas.invoice import InvoiceRead
from app.schemas.purchase_order import PurchaseOrderRead
from app.schemas.supplier import SupplierRead
from scripts.check_endpoints import read_response
from scripts.check_schema import TestTargetError, approved_test_url, require_test_marker, verify_revision

WORKSPACE = "00000000-0000-4000-8000-000000000001"
SUPPLIER = "10000000-0000-4000-8000-000000000001"
ORDER = "20000000-0000-4000-8000-000000000001"
ORDER_LINE = "21000000-0000-4000-8000-000000000001"
RECEIPT = "30000000-0000-4000-8000-000000000001"
RECEIPT_LINE = "31000000-0000-4000-8000-000000000001"
INVOICE = "40000000-0000-4000-8000-000000000001"
INVOICE_LINE = "41000000-0000-4000-8000-000000000001"
ERROR_CODES = {"422": "validation_error", "404": "not_found", "409": "conflict", "503": "service_unavailable", "500": "internal_error"}


class DemoCheckError(RuntimeError):
    pass


def require_disposable() -> None:
    # The settings guard runs before connecting or invoking the seeder. The
    # database's own marker confirms that it belongs to this exact check project.
    engine = create_database_engine(approved_test_url(os.environ))
    try:
        with engine.connect() as connection:
            require_test_marker(connection, os.environ)
            verify_revision(connection)
    finally:
        engine.dispose()


def seed_once() -> None:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "app.seed_demo"], check=True,
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        raise DemoCheckError("Explicit demo seed command failed or timed out; no persistence pass is claimed.") from None
    print(completed.stdout.strip())


def read_demo(base_url: str = "http://127.0.0.1:8000", *, timeout: float = 60) -> dict:
    if not 0 < timeout <= 60:
        raise DemoCheckError("Demo HTTP timeout must be positive and at most 60 seconds.")
    deadline = time.monotonic() + timeout

    def get(path):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DemoCheckError("Demo HTTP deadline reached.")
        status, body = read_response(base_url.rstrip("/") + path, remaining)
        if status != 200 or not isinstance(body, dict):
            raise DemoCheckError("A demo API read did not return its expected HTTP 200 object.")
        return body

    def subset(actual, expected):
        if any(actual.get(key) != value for key, value in expected.items()):
            raise DemoCheckError("Demo record IDs, links, fields, or decimal strings do not match the fixture.")

    details = {}
    for resource, record_id, schema in [
        ("suppliers", SUPPLIER, SupplierRead), ("purchase-orders", ORDER, PurchaseOrderRead),
        ("delivery-receipts", RECEIPT, DeliveryReceiptRead), ("invoices", INVOICE, InvoiceRead),
    ]:
        body = get(f"/{resource}/{record_id}")
        try:
            schema.model_validate(body)
        except ValueError:
            raise DemoCheckError("A demo response did not match its documented record schema.") from None
        subset(body, {"id": record_id, "workspace_id": WORKSPACE})
        details[resource] = body
    subset(details["suppliers"], {"supplier_code": "DEMO-OFFICE-001", "name": "Demo Office Supplies", "notes": "Fictional supplier for the local demonstration."})
    subset(details["purchase-orders"], {"supplier_id": SUPPLIER, "po_number": "PO-DEMO-001", "order_date": "2026-10-13", "currency": "EUR", "notes": None, "subtotal": "250.00"})
    subset(details["delivery-receipts"], {"purchase_order_id": ORDER, "receipt_number": "DR-DEMO-001", "received_date": "2026-10-14", "notes": None})
    subset(details["invoices"], {"supplier_id": SUPPLIER, "purchase_order_id": ORDER, "invoice_number": "INV-DEMO-001", "invoice_date": "2026-10-15", "due_date": "2026-11-14", "currency": "EUR", "status": "draft", "notes": None, "subtotal": "250.00", "tax_amount": "0.00", "total": "250.00"})
    lines = {
        "purchase-orders": {"id": ORDER_LINE, "purchase_order_id": ORDER, "description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000", "line_total": "250.00"},
        "delivery-receipts": {"id": RECEIPT_LINE, "delivery_receipt_id": RECEIPT, "purchase_order_id": ORDER, "purchase_order_line_id": ORDER_LINE, "quantity_received": "8.000"},
        "invoices": {"id": INVOICE_LINE, "invoice_id": INVOICE, "description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000", "line_total": "250.00", "purchase_order_line_id": ORDER_LINE},
    }
    for resource, expected in lines.items():
        if len(details[resource]["lines"]) != 1:
            raise DemoCheckError("A demo document does not have exactly its expected line.")
        subset(details[resource]["lines"][0], {**expected, "workspace_id": WORKSPACE, "line_no": 1})

    lists = {}
    filters = {
        "purchase-orders": f"&supplier_id={SUPPLIER}",
        "delivery-receipts": f"&purchase_order_id={ORDER}",
        "invoices": f"&supplier_id={SUPPLIER}&purchase_order_id={ORDER}",
    }
    for resource, body in details.items():
        summary = {key: value for key, value in body.items() if key != "lines"}
        for suffix in ("", filters[resource]) if resource in filters else ("",):
            path = f"/{resource}?limit=20&offset=0{suffix}"
            page = get(path)
            if page != {"items": [summary], "limit": 20, "offset": 0, "total": 1}:
                raise DemoCheckError("Demo list counts, header summaries, or scoped filters did not match.")
            lists[path] = page

    document = get("/openapi.json")
    try:
        for resource in details:
            for suffix, method in [("", "post"), ("", "get"), ("/{id}", "get")]:
                responses = document["paths"][f"/{resource}{suffix}"][method]["responses"]
                for status, code in ERROR_CODES.items():
                    if responses[status]["content"]["application/json"]["example"]["error"]["code"] != code:
                        raise DemoCheckError("Live OpenAPI business error examples have an incorrect status code.")
    except (KeyError, TypeError):
        raise DemoCheckError("Live OpenAPI business error examples are missing.") from None
    return {"details": details, "lists": lists}


def compare_snapshots(before: dict, after: dict) -> None:
    if before != after:
        raise DemoCheckError("Demo IDs, timestamps, fields, lines, or counts changed; verification failed.")


def print_returned_values(snapshot: dict) -> None:
    records = snapshot["details"]
    print(json.dumps({
        "returned_ids": {resource: record["id"] for resource, record in records.items()},
        "returned_line_ids": {resource: record["lines"][0]["id"] for resource, record in records.items() if "lines" in record},
        "ordered_quantity": records["purchase-orders"]["lines"][0]["quantity"],
        "received_quantity": records["delivery-receipts"]["lines"][0]["quantity_received"],
        "invoiced_quantity": records["invoices"]["lines"][0]["quantity"],
        "unit_price": records["invoices"]["lines"][0]["unit_price"],
        "tax_amount": records["invoices"]["tax_amount"], "total": records["invoices"]["total"], "status": records["invoices"]["status"],
    }, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capture", "verify"])
    parser.add_argument("--snapshot", type=Path, default=Path("/tmp/supplier-invoice-verification-demo.json"))
    args = parser.parse_args()
    try:
        require_disposable()
        if args.action == "capture":
            seed_once()
            first = read_demo()
            seed_once()
            second = read_demo()
            compare_snapshots(first, second)
            # The API container writable layer survives docker compose restart;
            # the PostgreSQL named volume must also survive until comparison.
            args.snapshot.write_text(json.dumps(second, sort_keys=True), encoding="utf-8")
            print_returned_values(second)
            print("Full demo seed repeated: live API IDs, timestamps, lines, values, and counts unchanged.")
        else:
            before = json.loads(args.snapshot.read_text(encoding="utf-8"))
            after = read_demo()
            compare_snapshots(before, after)
            print_returned_values(after)
            print("Persistence verified through the live API after API/PostgreSQL restart with their volume retained.")
    except (TestTargetError, DemoCheckError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except (SQLAlchemyError, OSError, ValueError):
        print("Disposable demo verification failed; check services, migrations, or the retained snapshot.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
