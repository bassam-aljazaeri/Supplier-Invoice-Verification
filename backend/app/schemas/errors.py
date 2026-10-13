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
    status: {"model": BusinessErrorResponse, "description": description}
    for status, description in {
        422: "Invalid request fields or incompatible references.",
        404: "Record or reference not found in the active workspace.",
        409: "Scoped identifier already exists.",
        503: "Service or local demo workspace unavailable.",
        500: "Unexpected failure; internal details are withheld.",
    }.items()
}
