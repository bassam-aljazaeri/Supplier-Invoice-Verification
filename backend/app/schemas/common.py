import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, WithJsonSchema,
    field_serializer,
)

from app.models.base import MONEY_MAX, PRICE_MAX, QUANTITY_MAX


def trim_text(value):
    return value.strip() if isinstance(value, str) else value


def normalize_notes(value):
    return (value.strip() or None) if isinstance(value, str) else value


Identifier = Annotated[str, BeforeValidator(trim_text), Field(strict=True, min_length=1, max_length=64)]
Name = Annotated[str, BeforeValidator(trim_text), Field(strict=True, min_length=1, max_length=200)]
Description = Annotated[str, BeforeValidator(trim_text), Field(strict=True, min_length=1, max_length=500)]
Notes = Annotated[Annotated[str, Field(strict=True, max_length=2000)] | None, BeforeValidator(normalize_notes)]


def decimal_string(value, *, scale: int, maximum: str, positive: bool) -> Decimal:
    if not isinstance(value, str) or not 1 <= len(value) <= 32:
        raise ValueError("Use a plain decimal string.")
    if re.fullmatch(rf"[0-9]+(?:\.[0-9]{{1,{scale}}})?", value) is None:
        raise ValueError("Use a plain decimal string with the allowed scale.")
    result = Decimal(value)
    if result > Decimal(maximum) or result < 0 or (positive and result == 0):
        raise ValueError("Decimal value is outside the allowed range.")
    return result


def quantity_string(value) -> Decimal:
    return decimal_string(value, scale=3, maximum=QUANTITY_MAX, positive=True)


def price_string(value) -> Decimal:
    return decimal_string(value, scale=4, maximum=PRICE_MAX, positive=False)


def money_string(value) -> Decimal:
    return decimal_string(value, scale=2, maximum=MONEY_MAX, positive=False)


QuantityInput = Annotated[
    Decimal, BeforeValidator(quantity_string),
    WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 32, "pattern": r"^[0-9]+(?:\.[0-9]{1,3})?$"}),
]
PriceInput = Annotated[
    Decimal, BeforeValidator(price_string),
    WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 32, "pattern": r"^[0-9]+(?:\.[0-9]{1,4})?$"}),
]
MoneyInput = Annotated[
    Decimal, BeforeValidator(money_string),
    WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 32, "pattern": r"^[0-9]+(?:\.[0-9]{1,2})?$"}),
]
QuantityRead = Annotated[Decimal, Field(gt=0, le=Decimal(QUANTITY_MAX)), PlainSerializer(lambda value: format(value, ".3f"), return_type=str)]
PriceRead = Annotated[Decimal, Field(ge=0, le=Decimal(PRICE_MAX)), PlainSerializer(lambda value: format(value, ".4f"), return_type=str)]
MoneyRead = Annotated[Decimal, Field(ge=0, le=Decimal(MONEY_MAX)), PlainSerializer(lambda value: format(value, ".2f"), return_type=str)]


def iso_date(value) -> date:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("Use a valid YYYY-MM-DD calendar date.")
    return date.fromisoformat(value)


DateInput = Annotated[date, BeforeValidator(iso_date)]


class CreateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    created_at: datetime

    @field_serializer("created_at")
    def utc_timestamp(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)


Item = TypeVar("Item")


class RecordList(BaseModel, Generic[Item]):
    items: list[Item]
    limit: int
    offset: int
    total: int
