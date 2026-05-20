from decimal import Decimal

import pytest

from services.payroll.calculator import (
    CompensationInput,
    PayrollInput,
    calculate_payslip,
)


def _input(**overrides):
    defaults = dict(
        pay_basis="fixed",
        base_salary=Decimal("100000"),
        hourly_rate=None,
        unit_rate=None,
        hours_worked=None,
        units_processed=None,
        bonuses=(),
        deductions=(),
        reimbursements=(),
        currency="PKR",
    )
    defaults.update(overrides)
    return PayrollInput(**defaults)


def test_fixed_salary_simple():
    r = calculate_payslip(_input())
    assert r.base_pay == Decimal("100000.00")
    assert r.net_pay == Decimal("100000.00")


def test_hourly_pay():
    r = calculate_payslip(_input(
        pay_basis="hourly", base_salary=None,
        hourly_rate=Decimal("500"), hours_worked=Decimal("160"),
    ))
    assert r.base_pay == Decimal("80000.00")
    assert r.net_pay == Decimal("80000.00")


def test_unit_pay():
    r = calculate_payslip(_input(
        pay_basis="unit", base_salary=None,
        unit_rate=Decimal("12.50"), units_processed=Decimal("4000"),
    ))
    assert r.base_pay == Decimal("50000.00")


def test_bonuses_and_reimbursements_increase_net():
    r = calculate_payslip(_input(
        bonuses=(CompensationInput("Eid bonus", Decimal("5000")),),
        reimbursements=(CompensationInput("Travel", Decimal("2500")),),
    ))
    assert r.bonuses_total == Decimal("5000.00")
    assert r.reimbursements_total == Decimal("2500.00")
    assert r.net_pay == Decimal("107500.00")


def test_deductions_reduce_net():
    r = calculate_payslip(_input(
        deductions=(
            CompensationInput("Pension", Decimal("8000")),
            CompensationInput("Late fee", Decimal("1500")),
        ),
    ))
    assert r.deductions_total == Decimal("9500.00")
    assert r.net_pay == Decimal("90500.00")


def test_combined_adjustments():
    r = calculate_payslip(_input(
        bonuses=(CompensationInput("Performance", Decimal("10000")),),
        deductions=(CompensationInput("Tax-like adjustment", Decimal("12000")),),
        reimbursements=(CompensationInput("Mobile bill", Decimal("3000")),),
    ))
    assert r.net_pay == Decimal("101000.00")


def test_quantization_rounds_half_up():
    r = calculate_payslip(_input(
        pay_basis="hourly", base_salary=None,
        hourly_rate=Decimal("12.345"), hours_worked=Decimal("1"),
    ))
    # 12.345 -> 12.35 (round half up)
    assert r.base_pay == Decimal("12.35")


def test_lines_include_one_per_input():
    r = calculate_payslip(_input(
        bonuses=(CompensationInput("A", Decimal("1")),),
        deductions=(CompensationInput("B", Decimal("2")),),
        reimbursements=(CompensationInput("C", Decimal("3")),),
    ))
    types = [ln.line_type for ln in r.lines]
    assert types == ["base", "bonus", "deduction", "reimbursement"]


def test_fixed_without_salary_raises():
    with pytest.raises(ValueError):
        calculate_payslip(_input(base_salary=None))


def test_hourly_without_rate_or_hours_raises():
    with pytest.raises(ValueError):
        calculate_payslip(_input(pay_basis="hourly", base_salary=None, hourly_rate=None))
    with pytest.raises(ValueError):
        calculate_payslip(_input(
            pay_basis="hourly", base_salary=None,
            hourly_rate=Decimal("100"), hours_worked=None,
        ))


def test_net_pay_money_redacts():
    r = calculate_payslip(_input())
    assert "100000" not in str(r.net_pay_money())
    assert "REDACTED" in str(r.net_pay_money())
