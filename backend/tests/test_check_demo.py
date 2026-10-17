import copy
import json
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from scripts import check_demo as checker


@pytest.fixture(autouse=True)
def synthetic_headers(monkeypatch):
    monkeypatch.setattr(checker, "authentication_headers", lambda: {"Authorization": "Bearer synthetic-unit-value", "X-Workspace-ID": checker.WORKSPACE})


@pytest.fixture
def demo_responses(monkeypatch):
    common = {"workspace_id": checker.WORKSPACE, "created_at": "2026-10-13T12:00:00Z"}
    records = {
        "suppliers": {**common, "id": checker.SUPPLIER, "supplier_code": "DEMO-OFFICE-001", "name": "Demo Office Supplies", "notes": "Fictional supplier for the local demonstration."},
        "purchase-orders": {**common, "id": checker.ORDER, "supplier_id": checker.SUPPLIER, "po_number": "PO-DEMO-001", "order_date": "2026-10-13", "currency": "EUR", "notes": None, "subtotal": "250.00", "lines": [
            {**common, "id": checker.ORDER_LINE, "purchase_order_id": checker.ORDER, "line_no": 1, "description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000", "line_total": "250.00"},
        ]},
        "delivery-receipts": {**common, "id": checker.RECEIPT, "purchase_order_id": checker.ORDER, "receipt_number": "DR-DEMO-001", "received_date": "2026-10-14", "notes": None, "lines": [
            {**common, "id": checker.RECEIPT_LINE, "delivery_receipt_id": checker.RECEIPT, "purchase_order_id": checker.ORDER, "purchase_order_line_id": checker.ORDER_LINE, "line_no": 1, "quantity_received": "8.000"},
        ]},
        "invoices": {**common, "id": checker.INVOICE, "supplier_id": checker.SUPPLIER, "purchase_order_id": checker.ORDER, "invoice_number": "INV-DEMO-001", "invoice_date": "2026-10-15", "due_date": "2026-11-14", "currency": "EUR", "status": "draft", "notes": None, "subtotal": "250.00", "tax_amount": "0.00", "total": "250.00", "lines": [
            {**common, "id": checker.INVOICE_LINE, "invoice_id": checker.INVOICE, "line_no": 1, "description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000", "line_total": "250.00", "purchase_order_line_id": checker.ORDER_LINE},
        ]},
    }
    paths = {}
    for resource in records:
        for suffix, method in [("", "post"), ("", "get"), ("/{id}", "get")]:
            paths.setdefault(f"/{resource}{suffix}", {})[method] = {"responses": {
                status: {"content": {"application/json": {"example": {"error": {"code": code}}}}}
                for status, code in checker.ERROR_CODES.items()
            }}
    document = {"paths": paths}
    calls = []

    def read_response(url, timeout, *, headers=None):
        parsed = urlsplit(url)
        if parsed.path != "/openapi.json":
            assert headers == {"Authorization": "Bearer synthetic-unit-value", "X-Workspace-ID": checker.WORKSPACE}
        calls.append((parsed.path, parsed.query, timeout))
        if parsed.path == "/openapi.json":
            return 200, copy.deepcopy(document)
        resource = parsed.path.split("/")[1]
        if parsed.query:
            summary = {key: value for key, value in records[resource].items() if key != "lines"}
            return 200, {"items": [copy.deepcopy(summary)], "limit": 20, "offset": 0, "total": 1}
        return 200, copy.deepcopy(records[resource])

    monkeypatch.setattr(checker, "read_response", read_response)
    return records, document, calls


def test_http_snapshot_checks_exact_decimals_all_details_lists_filters_and_examples(demo_responses):
    records, _, calls = demo_responses
    snapshot = checker.read_demo("http://demo.invalid/", timeout=1)
    assert snapshot["details"] == records
    assert len(snapshot["lists"]) == 7
    assert len(calls) == 12
    assert all(0 < timeout <= 1 for _, _, timeout in calls)
    assert any(f"supplier_id={checker.SUPPLIER}&purchase_order_id={checker.ORDER}" in query for _, query, _ in calls)


@pytest.mark.parametrize(("resource", "field", "value"), [
    ("invoices", "total", "250.01"), ("invoices", "total", 250),
    ("invoices", "status", "approved"), ("invoices", "due_date", "2026-11-15"),
    ("delivery-receipts", "purchase_order_id", checker.INVOICE),
    ("suppliers", "notes", "private-existing-value"),
])
def test_changed_or_invalid_record_fails_without_echoing_values(demo_responses, resource, field, value):
    records, _, _ = demo_responses
    records[resource][field] = value
    with pytest.raises(checker.DemoCheckError) as error:
        checker.read_demo()
    assert "private-existing-value" not in str(error.value)


@pytest.mark.parametrize(("field", "value"), [
    ("quantity_received", "9.000"), ("quantity_received", "8"),
    ("purchase_order_line_id", checker.INVOICE_LINE), ("line_no", 2),
])
def test_received_line_values_and_identity_must_match(demo_responses, field, value):
    records, _, _ = demo_responses
    records["delivery-receipts"]["lines"][0][field] = value
    with pytest.raises(checker.DemoCheckError):
        checker.read_demo()


def test_extra_lines_fail(demo_responses):
    records, _, _ = demo_responses
    records["invoices"]["lines"].append(copy.deepcopy(records["invoices"]["lines"][0]))
    with pytest.raises(checker.DemoCheckError, match="exactly"):
        checker.read_demo()


def test_bad_list_count_fails(demo_responses, monkeypatch):
    original = checker.read_response

    def read(url, timeout, *, headers=None):
        status, body = original(url, timeout, headers=headers)
        if "?" in url:
            body["total"] = 2
        return status, body

    monkeypatch.setattr(checker, "read_response", read)
    with pytest.raises(checker.DemoCheckError, match="counts"):
        checker.read_demo()


def test_incorrect_live_openapi_example_fails(demo_responses):
    _, document, _ = demo_responses
    document["paths"]["/invoices"]["post"]["responses"]["503"]["content"]["application/json"]["example"]["error"]["code"] = "validation_error"
    with pytest.raises(checker.DemoCheckError, match="incorrect status"):
        checker.read_demo()


@pytest.mark.parametrize("response", [(503, {"error": {"code": "service_unavailable"}}), (200, [])])
def test_non_success_or_non_object_fails(monkeypatch, response):
    monkeypatch.setattr(checker, "read_response", lambda *_, **__: response)
    with pytest.raises(checker.DemoCheckError, match="HTTP 200 object"):
        checker.read_demo()


def test_http_deadline_bounds_total_reads(demo_responses, monkeypatch):
    ticks = iter([0, 0.1, 1.1])
    monkeypatch.setattr(checker.time, "monotonic", lambda: next(ticks))
    with pytest.raises(checker.DemoCheckError, match="deadline"):
        checker.read_demo(timeout=1)
    assert len(demo_responses[2]) == 1


@pytest.mark.parametrize("timeout", [0, -1, 61])
def test_unbounded_timeout_is_rejected_before_http(demo_responses, timeout):
    with pytest.raises(checker.DemoCheckError, match="timeout"):
        checker.read_demo(timeout=timeout)
    assert demo_responses[2] == []


def test_capture_seeds_twice_and_verify_compares_without_reseeding(demo_responses, monkeypatch, tmp_path):
    snapshot = tmp_path / "demo.json"
    seeds = []
    guards = []
    monkeypatch.setattr(checker, "require_disposable", lambda: guards.append(True))
    monkeypatch.setattr(checker, "seed_once", lambda: seeds.append(True))
    monkeypatch.setattr(sys, "argv", ["check_demo", "capture", "--snapshot", str(snapshot)])
    assert checker.main() == 0
    assert len(seeds) == 2
    saved = json.loads(snapshot.read_text(encoding="utf-8"))
    assert saved["details"]["invoices"]["total"] == "250.00"
    monkeypatch.setattr(sys, "argv", ["check_demo", "verify", "--snapshot", str(snapshot)])
    assert checker.main() == 0
    assert len(seeds) == len(guards) == 2
    demo_responses[0]["invoices"]["created_at"] = "2026-10-16T12:00:00Z"
    assert checker.main() == 1
    assert len(seeds) == 2


@pytest.mark.parametrize("action", ["capture", "verify"])
def test_cli_refuses_without_opt_in_before_connection_seed_or_snapshot_access(monkeypatch, tmp_path, capsys, action):
    monkeypatch.delenv("RUN_POSTGRES_TESTS", raising=False)
    monkeypatch.setattr(checker, "create_database_engine", lambda *_: pytest.fail("unsafe connection"))
    monkeypatch.setattr(checker, "seed_once", lambda: pytest.fail("unsafe seed"))
    snapshot = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(sys, "argv", ["check_demo", action, "--snapshot", str(snapshot)])
    assert checker.main() == 1
    assert not snapshot.exists()
    assert "RUN_POSTGRES_TESTS=1" in capsys.readouterr().err


def test_seed_checker_invokes_explicit_module_with_bounded_timeout(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="Synthetic fixture saved.\n")

    monkeypatch.setattr(checker.subprocess, "run", run)
    checker.seed_once()
    assert calls == [([sys.executable, "-m", "app.seed_demo"], {"check": True, "capture_output": True, "text": True, "timeout": 30})]


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("seed", 30), subprocess.CalledProcessError(1, "seed", stderr="private-existing-value"), OSError("private-existing-value")])
def test_seed_failure_is_sanitized_and_never_claims_success(monkeypatch, error):
    def fail(*_, **__):
        raise error

    monkeypatch.setattr(checker.subprocess, "run", fail)
    with pytest.raises(checker.DemoCheckError, match="no persistence pass") as captured:
        checker.seed_once()
    assert "private-existing-value" not in str(captured.value)
