from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator

from app.schemas.common import (
    CreateModel, DateInput, Description, Identifier, MoneyInput, MoneyRead, Notes,
    Pagination, PriceInput, PriceRead, QuantityInput, QuantityRead, ReadRecord,
    RecordList,
)


class InvoiceLineCreate(CreateModel):
    description: Description
    quantity: QuantityInput
    unit_price: PriceInput
    purchase_order_line_id: UUID | None = None


class InvoiceCreate(CreateModel):
    supplier_id: UUID
    purchase_order_id: UUID | None = None
    invoice_number: Identifier
    invoice_date: DateInput
    due_date: DateInput | None = None
    currency: Literal["EUR"]
    tax_amount: MoneyInput
    notes: Notes = None
    lines: Annotated[list[InvoiceLineCreate], Field(min_length=1, max_length=100)]

    @field_validator("due_date")
    @classmethod
    def due_date_not_before_invoice(cls, value: date | None, info: ValidationInfo):
        invoice_date = info.data.get("invoice_date")
        if value is not None and invoice_date is not None and value < invoice_date:
            raise ValueError("Due date must not precede the invoice date.")
        return value


class InvoiceLineRead(ReadRecord):
    invoice_id: UUID
    line_no: int
    description: str
    quantity: QuantityRead
    unit_price: PriceRead
    line_total: MoneyRead
    purchase_order_line_id: UUID | None


class InvoiceSummary(ReadRecord):
    supplier_id: UUID
    purchase_order_id: UUID | None
    invoice_number: str
    invoice_date: date
    due_date: date | None
    currency: Literal["EUR"]
    status: Literal["draft"]
    notes: str | None
    subtotal: MoneyRead
    tax_amount: MoneyRead
    total: MoneyRead


class InvoiceRead(InvoiceSummary):
    lines: list[InvoiceLineRead]


class InvoiceList(RecordList[InvoiceSummary]):
    pass


class InvoiceQuery(Pagination):
    supplier_id: UUID | None = None
    purchase_order_id: UUID | None = None
