"""Deterministic money arithmetic.

All monetary values are ``Decimal``. Floats are rejected at the boundary so that
binary rounding can never leak into risk calculations.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation

PAISE = Decimal("0.01")
ZERO = Decimal("0")


def to_dec(value: object) -> Decimal:
    """Convert int/str/Decimal to Decimal. Floats are refused (use strings)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a monetary value")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal: {value!r}") from exc
    if isinstance(value, float):
        raise TypeError("floats are not accepted for money/risk values; pass a string")
    raise TypeError(f"cannot convert {type(value).__name__} to Decimal")


def floor_int(value: Decimal) -> int:
    """Round DOWN to an integer. The only rounding used in position sizing."""
    if value.is_nan() or value.is_infinite():
        raise ValueError("cannot floor a non-finite value")
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def paise(value: Decimal) -> Decimal:
    """Quantize to paise (used for ledger allocations and display only)."""
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def fmt_inr(value: Decimal) -> str:
    q = paise(value)
    sign = "-" if q < 0 else ""
    return f"{sign}₹{abs(q):,.2f}"


def fmt_pct(value: Decimal) -> str:
    return f"{(value * 100).quantize(Decimal('0.01'))}%"
