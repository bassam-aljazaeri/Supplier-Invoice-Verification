from typing import Literal

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["validation_error", "not_found", "conflict", "service_unavailable", "internal_error"]
    message: str
    details: list[ErrorDetail]


class BusinessErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


BUSINESS_ERROR_RESPONSES = {
    status: {
        "model": BusinessErrorResponse, "description": description,
        "content": {"application/json": {"example": {"error": {"code": code, "message": message, "details": []}}}},
    }
    for status, (description, code, message) in {
        422: ("Invalid request fields or incompatible references.", "validation_error", "Some fields are invalid."),
        404: ("Record or reference not found in the active workspace.", "not_found", "The record was not found."),
        409: ("Scoped identifier already exists.", "conflict", "A record with this identifier already exists."),
        503: ("Service or local demo workspace unavailable.", "service_unavailable", "The service is temporarily unavailable."),
        500: ("Unexpected failure; internal details are withheld.", "internal_error", "The request could not be completed."),
    }.items()
}
