"""Pure payroll calculation.

Inputs are passed in explicitly (not pulled from the ORM). The function is free
of side effects: no DB, no IO. The Django-facing wrapper in apps.payroll.services
is responsible for fetching inputs, calling this, and persisting Payslips.

This separation makes payroll math straightforward to test and audit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from domain.money import Money


@dataclass(frozen=True, slots=True)
class CompensationInput:
    description: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PayrollInput:
    """All inputs required to compute one Payslip."""

    pay_basis: str  # one of "fixed", "hourly", "unit"
    base_salary: Decimal | None
    hourly_rate: Decimal | None
    unit_rate: Decimal | None
    hours_worked: Decimal | None
    units_processed: Decimal | None
    bonuses: Sequence[CompensationInput] = field(default_factory=tuple)
    deductions: Sequence[CompensationInput] = field(default_factory=tuple)
    reimbursements: Sequence[CompensationInput] = field(default_factory=tuple)
    currency: str = "PKR"


@dataclass(frozen=True, slots=True)
class PayslipLineResult:
    line_type: str  # "base" | "bonus" | "deduction" | "reimbursement"
    description: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PayslipResult:
    base_pay: Decimal
    bonuses_total: Decimal
    deductions_total: Decimal
    reimbursements_total: Decimal
    net_pay: Decimal
    currency: str
    lines: tuple[PayslipLineResult, ...]

    def net_pay_money(self) -> Money:
        return Money(self.net_pay, self.currency)


_TWO_PLACES = Decimal("0.01")


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _compute_base(input_: PayrollInput) -> tuple[Decimal, str]:
    """Return (base_pay, description) per the pay basis."""
    if input_.pay_basis == "fixed":
        if input_.base_salary is None:
            raise ValueError("base_salary is required for fixed pay basis.")
        return _quantize(input_.base_salary), "Fixed monthly salary"
    if input_.pay_basis == "hourly":
        if input_.hourly_rate is None or input_.hours_worked is None:
            raise ValueError("hourly_rate and hours_worked are required for hourly pay basis.")
        return (
            _quantize(input_.hourly_rate * input_.hours_worked),
            f"Hourly pay ({input_.hours_worked} h @ {input_.currency})",
        )
    if input_.pay_basis == "unit":
        if input_.unit_rate is None or input_.units_processed is None:
            raise ValueError("unit_rate and units_processed are required for unit pay basis.")
        return (
            _quantize(input_.unit_rate * input_.units_processed),
            f"Unit-based pay ({input_.units_processed} units @ {input_.currency})",
        )
    raise ValueError(f"Unknown pay_basis: {input_.pay_basis!r}")


def calculate_payslip(input_: PayrollInput) -> PayslipResult:
    """Pure payroll computation. No IO, no Django."""
    base, base_description = _compute_base(input_)

    lines: list[PayslipLineResult] = [
        PayslipLineResult("base", base_description, base),
    ]

    bonuses_total = Decimal("0")
    for b in input_.bonuses:
        amount = _quantize(b.amount)
        bonuses_total += amount
        lines.append(PayslipLineResult("bonus", b.description, amount))

    deductions_total = Decimal("0")
    for d in input_.deductions:
        amount = _quantize(d.amount)
        deductions_total += amount
        lines.append(PayslipLineResult("deduction", d.description, amount))

    reimbursements_total = Decimal("0")
    for r in input_.reimbursements:
        amount = _quantize(r.amount)
        reimbursements_total += amount
        lines.append(PayslipLineResult("reimbursement", r.description, amount))

    net_pay = _quantize(base + bonuses_total + reimbursements_total - deductions_total)

    return PayslipResult(
        base_pay=base,
        bonuses_total=bonuses_total,
        deductions_total=deductions_total,
        reimbursements_total=reimbursements_total,
        net_pay=net_pay,
        currency=input_.currency,
        lines=tuple(lines),
    )
