"""Currency-amount value type with redacted repr/str.

`Money` is the only type that carries currency amounts inside payroll calculations.
Its `__repr__` and `__str__` always redact the value, so an accidental
`logger.info("%s", payslip.net_pay)` never leaks an amount. Use `.amount` explicitly
to render a value, and route any rendered amount through an audit-aware writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

ALLOWED_CURRENCIES: Final[frozenset[str]] = frozenset({"PKR", "ETB"})


@dataclass(frozen=True, slots=True, repr=False)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money.amount must be a Decimal.")
        if self.currency not in ALLOWED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {self.currency!r}")

    def __repr__(self) -> str:
        # __repr__/__str__ stay redacted so accidental log interpolation never leaks.
        return f"<Money {self.currency} REDACTED>"

    def __str__(self) -> str:
        return self.__repr__()

    def format(self) -> str:
        """Human-readable display: 'PKR 12,345.67'. Use in trusted UI surfaces only."""
        return f"{self.currency} {self.amount:,.2f}"

    def __add__(self, other: Money) -> Money:
        self._check_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Decimal | int) -> Money:
        return Money(self.amount * Decimal(factor), self.currency)

    def __rmul__(self, factor: Decimal | int) -> Money:
        return self.__mul__(factor)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def _check_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot combine {self.currency} with {other.currency}."
            )
