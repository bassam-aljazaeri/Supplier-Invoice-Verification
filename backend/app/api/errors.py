from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError, TimeoutError

from app.schemas.errors import BUSINESS_ERROR_RESPONSES


class BusinessError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list[dict[str, str]] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []

    def response(self) -> JSONResponse:
        return JSONResponse(status_code=self.status, content={"error": {
            "code": self.code, "message": self.message, "details": self.details,
        }}, headers={"Cache-Control": "no-store", **({"WWW-Authenticate": "Bearer"} if self.status == 401 else {})})


def unauthorized() -> BusinessError:
    return BusinessError(401, "unauthorized", "Valid authentication is required.")


def forbidden() -> BusinessError:
    return BusinessError(403, "forbidden", "You do not have permission for this request.")


def unavailable() -> BusinessError:
    return BusinessError(503, "service_unavailable", "The service is temporarily unavailable.")


def invalid(field: str, message: str) -> BusinessError:
    return BusinessError(422, "validation_error", "Some fields are invalid.", [{"field": field, "message": message}])


def missing(kind: str, field: str = "id") -> BusinessError:
    return BusinessError(404, "not_found", f"The {kind} was not found.", [{"field": field, "message": f"Choose an available {kind}."}])


# Unknown keys and validation inputs are untrusted; never echo them or Pydantic's
# input/ctx/msg fields. Only known schema field labels and constant messages return.
SAFE_FIELDS = {
    "id", "workspace_id", "created_at", "supplier_code", "name", "notes",
    "supplier_id", "po_number", "order_date", "currency", "lines", "quantity",
    "unit_price", "description", "line_no", "line_total", "subtotal", "status", "limit", "offset",
    "purchase_order_id", "purchase_order_line_id", "receipt_number", "received_date",
    "delivery_receipt_id", "quantity_received", "invoice_id", "invoice_number",
    "invoice_date", "due_date", "tax_amount", "total",
    "slug", "application_user_id", "role",
}


def safe_field(location: tuple) -> str:
    result = ""
    for part in location:
        if part in ("body", "query", "path"):
            continue
        if isinstance(part, int) and result:
            result += f"[{part}]"
        elif isinstance(part, str) and part in SAFE_FIELDS:
            result += ("." if result else "") + part
        else:
            return "request"
    return result or "request"


def validation_response(error: RequestValidationError) -> JSONResponse:
    details = []
    for item in error.errors():
        field = safe_field(item["loc"])
        kind = item["type"]
        if kind == "extra_forbidden":
            message = "This field is not allowed."
        elif kind == "missing":
            message = "This field is required."
        elif kind == "json_invalid":
            message = "Submit valid JSON."
        elif kind.startswith("uuid"):
            message = "Use a valid UUID."
        elif kind.startswith("int") or kind in {"greater_than_equal", "less_than_equal"}:
            message = "Use an integer within the allowed bounds."
        elif kind in {"too_short", "too_long", "list_type"}:
            message = "Provide between 1 and 100 line items."
        elif field.endswith(("quantity", "quantity_received")):
            message = "Use a positive decimal string within the quantity bounds and at most 3 fractional digits."
        elif field.endswith("unit_price"):
            message = "Use a nonnegative decimal string within the price bounds and at most 4 fractional digits."
        elif field == "tax_amount":
            message = "Use a nonnegative decimal string within the monetary bounds and at most 2 fractional digits."
        elif field == "due_date":
            message = "Use a valid YYYY-MM-DD calendar date on or after invoice_date, or null."
        elif field in {"order_date", "received_date", "invoice_date"}:
            message = "Use a valid YYYY-MM-DD calendar date."
        elif field == "currency":
            message = "Use EUR."
        else:
            message = "Use a value of the required type and allowed length; required text must not be blank."
        details.append({"field": field, "message": message})
    return BusinessError(422, "validation_error", "Some fields are invalid.", details).response()


class BusinessRoute(APIRoute):
    """Authenticate and authorize before body parsing; preserve safe errors."""

    workspace_mode = "business"

    def __init__(self, *args, **kwargs):
        # Explicit 422 replaces FastAPI's default detail schema in OpenAPI.
        kwargs["responses"] = {**(kwargs.get("responses") or {}), **BUSINESS_ERROR_RESPONSES}
        kwargs["dependencies"] = [*(kwargs.get("dependencies") or []), Depends(HTTPBearer(auto_error=False, scheme_name="BearerAuth"))]
        super().__init__(*args, **kwargs)

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                from app.api.authorization import authorized_request

                async with authorized_request(request, self.workspace_mode):
                    if "workspace_id" in request.query_params:
                        raise invalid("workspace_id", "This field is not allowed.")
                    response = await original_handler(request)
                    response.headers["Cache-Control"] = "no-store"
                    return response
            except RequestValidationError as error:
                return validation_response(error)
            except BusinessError as error:
                return error.response()
            except (OperationalError, InterfaceError, DisconnectionError, TimeoutError):
                return unavailable().response()
            except Exception:
                return BusinessError(500, "internal_error", "The request could not be completed.").response()

        return handler


class AccountRoute(BusinessRoute):
    workspace_mode = "none"


class MembershipRoute(BusinessRoute):
    workspace_mode = "path"
