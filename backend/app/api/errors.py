from collections.abc import Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError, TimeoutError


class BusinessError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list[dict[str, str]] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []

    def response(self) -> JSONResponse:
        return JSONResponse(status_code=self.status, content={"error": {
            "code": self.code, "message": self.message, "details": self.details,
        }})


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
    "purchase_order_id",
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
        elif field.endswith("quantity"):
            message = "Use a positive decimal string within the quantity bounds and at most 3 fractional digits."
        elif field.endswith("unit_price"):
            message = "Use a nonnegative decimal string within the price bounds and at most 4 fractional digits."
        elif field == "order_date":
            message = "Use a valid YYYY-MM-DD calendar date."
        elif field == "currency":
            message = "Use EUR."
        else:
            message = "Use a value of the required type and allowed length; required text must not be blank."
        details.append({"field": field, "message": message})
    return BusinessError(422, "validation_error", "Some fields are invalid.", details).response()


class BusinessRoute(APIRoute):
    """Sanitize business errors without changing foundation endpoint handlers."""

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                if "workspace_id" in request.query_params:
                    raise invalid("workspace_id", "This field is not allowed.")
                return await original_handler(request)
            except RequestValidationError as error:
                return validation_response(error)
            except BusinessError as error:
                return error.response()
            except (OperationalError, InterfaceError, DisconnectionError, TimeoutError):
                return unavailable().response()
            except Exception:
                return BusinessError(500, "internal_error", "The request could not be completed.").response()

        return handler
