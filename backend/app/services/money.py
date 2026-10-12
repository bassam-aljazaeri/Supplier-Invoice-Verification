from collections.abc import Iterable
from decimal import Decimal, ROUND_HALF_UP, localcontext

from app.models.base import MONEY_MAX, PRICE_MAX, QUANTITY_MAX

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal(MONEY_MAX)


class MoneyError(ValueError):
    pass


def calculate_line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    if (
        not isinstance(quantity, Decimal) or not isinstance(unit_price, Decimal)
        or not quantity.is_finite() or not unit_price.is_finite()
        or not 0 < quantity <= Decimal(QUANTITY_MAX)
        or not 0 <= unit_price <= Decimal(PRICE_MAX)
    ):
        raise MoneyError("Invalid quantity or unit price.")
    with localcontext() as context:
        context.prec = 38
        amount = (quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
    if amount > MAX_AMOUNT:
        raise MoneyError("Calculated line total exceeds the supported monetary range.")
    return amount


def sum_line_totals(line_totals: Iterable[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = 38
        total = Decimal("0.00")
        for amount in line_totals:
            if not isinstance(amount, Decimal) or not amount.is_finite() or not 0 <= amount <= MAX_AMOUNT:
                raise MoneyError("Invalid line total.")
            if amount != amount.quantize(CENT, rounding=ROUND_HALF_UP):
                raise MoneyError("Line totals must already be rounded to cents.")
            total += amount
            if total > MAX_AMOUNT:
                raise MoneyError("Calculated subtotal exceeds the supported monetary range.")
        return total.quantize(CENT, rounding=ROUND_HALF_UP)
