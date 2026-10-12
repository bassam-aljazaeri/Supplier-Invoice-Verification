from decimal import Decimal, ROUND_DOWN, localcontext

import pytest
from pydantic import ValidationError

from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.money import MAX_AMOUNT, MoneyError, calculate_line_total, sum_line_totals


def order_payload(**overrides):
    return {
        "supplier_id": "10000000-0000-4000-8000-000000000001",
        "po_number": "PO-001", "order_date": "2026-10-13", "currency": "EUR",
        "lines": [{"description": "Keyboard", "quantity": "10", "unit_price": "25"}],
    } | overrides


def test_round_each_line_before_summing_and_ignore_callers_decimal_context():
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_DOWN
        totals = [calculate_line_total(Decimal("0.001"), Decimal("5")) for _ in range(2)]
        assert totals == [Decimal("0.01"), Decimal("0.01")]
        assert sum_line_totals(totals) == Decimal("0.02")
        assert calculate_line_total(Decimal("1"), Decimal("1.0050")) == Decimal("1.01")


def test_money_bounds_and_calculated_overflow():
    assert calculate_line_total(Decimal("10"), Decimal("25")) == Decimal("250.00")
    assert calculate_line_total(Decimal("0.001"), Decimal("0")) == Decimal("0.00")
    assert sum_line_totals([MAX_AMOUNT]) == MAX_AMOUNT
    with pytest.raises(MoneyError, match="line total exceeds"):
        calculate_line_total(Decimal("999999999.999"), Decimal("9999999999.9999"))
    with pytest.raises(MoneyError, match="subtotal exceeds"):
        sum_line_totals([MAX_AMOUNT, Decimal("0.01")])


@pytest.mark.parametrize(("quantity", "price"), [
    (1.0, Decimal("1")), (Decimal("1"), 1.0),
    (Decimal("0"), Decimal("1")), (Decimal("-1"), Decimal("1")),
    (Decimal("NaN"), Decimal("1")), (Decimal("1"), Decimal("Infinity")),
    (Decimal("1"), Decimal("-1")),
])
def test_helpers_reject_non_decimal_or_invalid_values(quantity, price):
    with pytest.raises(MoneyError):
        calculate_line_total(quantity, price)


@pytest.mark.parametrize("amount", [0.1, Decimal("-1"), Decimal("NaN"), Decimal("0.005")])
def test_subtotal_requires_finite_nonnegative_cent_amounts(amount):
    with pytest.raises(MoneyError):
        sum_line_totals([amount])


@pytest.mark.parametrize("value", [
    10, 10.0, True, None, "", " 10", "10 ", "+10", "-10", "1e1", "NaN",
    "Infinity", "1,000", ".1", "1.", "١٠", "0", "0.000", "1.0000",
    "1000000000", "0" * 33 + "1",
])
def test_quantity_request_contract_is_strict(value):
    payload = order_payload(lines=[{"description": "Keyboard", "quantity": value, "unit_price": "25"}])
    with pytest.raises(ValidationError):
        PurchaseOrderCreate.model_validate(payload)


@pytest.mark.parametrize("value", [25, "-1", " 25", "2.5e1", "NaN", "Infinity", "1.00000", "10000000000"])
def test_price_request_contract_is_strict(value):
    payload = order_payload(lines=[{"description": "Keyboard", "quantity": "10", "unit_price": value}])
    with pytest.raises(ValidationError):
        PurchaseOrderCreate.model_validate(payload)


@pytest.mark.parametrize("value", ["2026-02-30", "20261013", "2026-1-1", "2026-10-13T00:00:00Z", " 2026-10-13", 20261013])
def test_order_dates_require_exact_calendar_dates(value):
    with pytest.raises(ValidationError):
        PurchaseOrderCreate.model_validate(order_payload(order_date=value))
