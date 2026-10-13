"""Published business errors describe their runtime envelope, including old routes."""

import json

import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api.errors import BusinessError, validation_response
from app.main import app
from app.schemas.errors import BusinessErrorResponse


@pytest.fixture(scope="module")
def openapi():
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        return response.json()


@pytest.mark.parametrize("resource", ["suppliers", "purchase-orders", "delivery-receipts", "invoices"])
@pytest.mark.parametrize(("suffix", "method", "success"), [("", "post", "201"), ("", "get", "200"), ("/{id}", "get", "200")])
def test_all_business_operations_document_actual_error_envelope(openapi, resource, suffix, method, success):
    responses = openapi["paths"][f"/{resource}{suffix}"][method]["responses"]
    assert success in responses
    for status in ("422", "404", "409", "503", "500"):
        assert responses[status]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/BusinessErrorResponse"}
    assert "HTTPValidationError" not in json.dumps(responses)


def test_published_error_fields_match_runtime_errors(openapi):
    components = openapi["components"]["schemas"]
    for name, required in [("BusinessErrorResponse", {"error"}), ("ErrorBody", {"code", "message", "details"}), ("ErrorDetail", {"field", "message"})]:
        assert set(components[name]["properties"]) == required
        assert set(components[name]["required"]) == required
        assert components[name]["additionalProperties"] is False
    assert components["ErrorBody"]["properties"]["details"]["type"] == "array"
    assert components["ErrorBody"]["properties"]["details"]["items"] == {"$ref": "#/components/schemas/ErrorDetail"}
    for status, code in [(422, "validation_error"), (404, "not_found"), (409, "conflict"), (503, "service_unavailable"), (500, "internal_error")]:
        content = json.loads(BusinessError(status, code, "Constant message").response().body)
        assert BusinessErrorResponse.model_validate(content).model_dump() == content
        assert code in components["ErrorBody"]["properties"]["code"]["enum"]
    content = json.loads(validation_response(RequestValidationError([
        {"loc": ("body", "lines", 0, "quantity_received"), "type": "value_error", "input": "private-value", "msg": "private-value"},
    ])).body)
    assert BusinessErrorResponse.model_validate(content).model_dump() == content
    assert "private-value" not in json.dumps(content)


@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_foundation_openapi_contract_is_preserved(openapi, path):
    responses = openapi["paths"][path]["get"]["responses"]
    assert set(responses) == {"200"}
    schema = responses["200"]["content"]["application/json"]["schema"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] == {"type": "string"}
    assert "BusinessErrorResponse" not in json.dumps(responses)


def test_new_request_and_response_documentation_exposes_only_allowed_fields(openapi):
    schemas = openapi["components"]["schemas"]
    invoice = schemas["InvoiceCreate"]
    assert "tax_amount" in invoice["required"]
    assert invoice["properties"]["tax_amount"]["type"] == "string"
    for name in ("DeliveryReceiptCreate", "DeliveryReceiptLineCreate", "InvoiceCreate", "InvoiceLineCreate"):
        assert schemas[name]["additionalProperties"] is False
        assert {"id", "workspace_id", "created_at", "status", "subtotal", "total", "line_total", "line_no"}.isdisjoint(schemas[name]["properties"])
    for name in ("InvoiceLineCreate", "InvoiceLineRead", "DeliveryReceiptLineCreate"):
        assert "purchase_order_id" not in schemas[name]["properties"]
    assert "purchase_order_id" in schemas["DeliveryReceiptLineRead"]["properties"]
    assert schemas["DeliveryReceiptLineCreate"]["properties"]["quantity_received"]["type"] == "string"
    assert schemas["InvoiceLineCreate"]["properties"]["quantity"]["type"] == "string"
    assert schemas["InvoiceLineCreate"]["properties"]["unit_price"]["type"] == "string"
