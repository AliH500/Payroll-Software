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
    """All inputs required to compute one Payslip.

    Every employee is salaried. Conveyance and attendance allowances roll into
    allowances_total; the performance bonus rolls into bonuses_total alongside any
    period-level bonuses.
    """

    salary: Decimal
    conveyance_allowance: Decimal = Decimal("0")
    attendance_allowance: Decimal = Decimal("0")
    performance_bonus: Decimal = Decimal("0")
    bonuses: Sequence[CompensationInput] = field(default_factory=tuple)
    deductions: Sequence[CompensationInput] = field(default_factory=tuple)
    reimbursements: Sequence[CompensationInput] = field(default_factory=tuple)
    currency: str = "PKR"


@dataclass(frozen=True, slots=True)
class PayslipLineResult:
    line_type: str  # "base" | "allowance" | "bonus" | "deduction" | "reimbursement"
    description: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PayslipResult:
    base_pay: Decimal
    allowances_total: Decimal
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


def calculate_payslip(input_: PayrollInput) -> PayslipResult:
    """Pure payroll computation. No IO, no Django."""
    base = _quantize(input_.salary)
    lines: list[PayslipLineResult] = [
        PayslipLineResult("base", "Monthly salary", base),
    ]

    # Structural allowances — kept in their own subtotal, separate from bonuses.
    allowances_total = Decimal("0")
    for description, amount in (
        ("Conveyance allowance", input_.conveyance_allowance),
        ("Attendance allowance", input_.attendance_allowance),
    ):
        quantized = _quantize(amount)
        if quantized == 0:
            continue
        allowances_total += quantized
        lines.append(PayslipLineResult("allowance", description, quantized))

    bonuses_total = Decimal("0")
    performance = _quantize(input_.performance_bonus)
    if performance != 0:
        bonuses_total += performance
        lines.append(PayslipLineResult("bonus", "Performance bonus", performance))
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

    net_pay = _quantize(
        base + allowances_total + bonuses_total + reimbursements_total - deductions_total
    )

    return PayslipResult(
        base_pay=base,
        allowances_total=allowances_total,
        bonuses_total=bonuses_total,
        deductions_total=deductions_total,
        reimbursements_total=reimbursements_total,
        net_pay=net_pay,
        currency=input_.currency,
        lines=tuple(lines),
    )
