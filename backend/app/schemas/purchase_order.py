from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    CreateModel, DateInput, Description, Identifier, MoneyRead, Notes, Pagination,
    PriceInput, PriceRead, QuantityInput, QuantityRead, ReadRecord, RecordList,
)


class PurchaseOrderLineCreate(CreateModel):
    description: Description
    quantity: QuantityInput
    unit_price: PriceInput


class PurchaseOrderCreate(CreateModel):
    supplier_id: UUID
    po_number: Identifier
    order_date: DateInput
    currency: Literal["EUR"]
    notes: Notes = None
    lines: Annotated[list[PurchaseOrderLineCreate], Field(min_length=1, max_length=100)]


class PurchaseOrderLineRead(ReadRecord):
    purchase_order_id: UUID
    line_no: int
    description: str
    quantity: QuantityRead
    unit_price: PriceRead
    line_total: MoneyRead


class PurchaseOrderSummary(ReadRecord):
    supplier_id: UUID
    po_number: str
    order_date: date
    currency: Literal["EUR"]
    notes: str | None
    subtotal: MoneyRead


class PurchaseOrderRead(PurchaseOrderSummary):
    lines: list[PurchaseOrderLineRead]


class PurchaseOrderList(RecordList[PurchaseOrderSummary]):
    pass


class PurchaseOrderQuery(Pagination):
    supplier_id: UUID | None = None
