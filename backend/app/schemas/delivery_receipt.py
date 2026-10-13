from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    CreateModel, DateInput, Identifier, Notes, Pagination, QuantityInput,
    QuantityRead, ReadRecord, RecordList,
)


class DeliveryReceiptLineCreate(CreateModel):
    purchase_order_line_id: UUID
    quantity_received: QuantityInput


class DeliveryReceiptCreate(CreateModel):
    purchase_order_id: UUID
    receipt_number: Identifier
    received_date: DateInput
    notes: Notes = None
    lines: Annotated[list[DeliveryReceiptLineCreate], Field(min_length=1, max_length=100)]


class DeliveryReceiptLineRead(ReadRecord):
    delivery_receipt_id: UUID
    purchase_order_id: UUID
    purchase_order_line_id: UUID
    line_no: int
    quantity_received: QuantityRead


class DeliveryReceiptSummary(ReadRecord):
    purchase_order_id: UUID
    receipt_number: str
    received_date: date
    notes: str | None


class DeliveryReceiptRead(DeliveryReceiptSummary):
    lines: list[DeliveryReceiptLineRead]


class DeliveryReceiptList(RecordList[DeliveryReceiptSummary]):
    pass


class DeliveryReceiptQuery(Pagination):
    purchase_order_id: UUID | None = None
