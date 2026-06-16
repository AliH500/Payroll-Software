from decimal import Decimal

from services.payroll.calculator import (
    CompensationInput,
    PayrollInput,
    calculate_payslip,
)


def _input(**overrides):
    defaults = dict(
        salary=Decimal("100000"),
        conveyance_allowance=Decimal("0"),
        attendance_allowance=Decimal("0"),
        performance_bonus=Decimal("0"),
        bonuses=(),
        deductions=(),
        reimbursements=(),
        currency="PKR",
    )
    defaults.update(overrides)
    return PayrollInput(**defaults)


def test_salary_only():
    r = calculate_payslip(_input())
    assert r.base_pay == Decimal("100000.00")
    assert r.allowances_total == Decimal("0.00")
    assert r.net_pay == Decimal("100000.00")
    assert [ln.line_type for ln in r.lines] == ["base"]


def test_allowances_roll_into_allowances_total():
    r = calculate_payslip(_input(
        conveyance_allowance=Decimal("5000"),
        attendance_allowance=Decimal("3000"),
    ))
    assert r.allowances_total == Decimal("8000.00")
    assert r.bonuses_total == Decimal("0.00")
    assert r.net_pay == Decimal("108000.00")
    types = [ln.line_type for ln in r.lines]
    assert types == ["base", "allowance", "allowance"]


def test_zero_allowance_emits_no_line():
    r = calculate_payslip(_input(
        conveyance_allowance=Decimal("0"),
        attendance_allowance=Decimal("2000"),
    ))
    descriptions = [ln.description for ln in r.lines]
    assert "Conveyance allowance" not in descriptions
    assert "Attendance allowance" in descriptions


def test_performance_bonus_rolls_into_bonuses_total():
    r = calculate_payslip(_input(performance_bonus=Decimal("8000")))
    assert r.allowances_total == Decimal("0.00")
    assert r.bonuses_total == Decimal("8000.00")
    assert r.net_pay == Decimal("108000.00")
    assert [ln.line_type for ln in r.lines] == ["base", "bonus"]


def test_period_bonuses_and_reimbursements_increase_net():
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


def test_combined_components():
    r = calculate_payslip(_input(
        conveyance_allowance=Decimal("4000"),
        attendance_allowance=Decimal("1000"),
        performance_bonus=Decimal("10000"),
        bonuses=(CompensationInput("Eid bonus", Decimal("5000")),),
        deductions=(CompensationInput("Pension", Decimal("12000")),),
        reimbursements=(CompensationInput("Mobile bill", Decimal("3000")),),
    ))
    # 100000 + (4000+1000) allowances + (10000+5000) bonuses + 3000 reimb - 12000 ded
    assert r.allowances_total == Decimal("5000.00")
    assert r.bonuses_total == Decimal("15000.00")
    assert r.net_pay == Decimal("111000.00")


def test_quantization_rounds_half_up():
    r = calculate_payslip(_input(salary=Decimal("12.345")))
    assert r.base_pay == Decimal("12.35")


def test_line_order():
    r = calculate_payslip(_input(
        conveyance_allowance=Decimal("1"),
        performance_bonus=Decimal("2"),
        bonuses=(CompensationInput("Period bonus", Decimal("3")),),
        deductions=(CompensationInput("Ded", Decimal("4")),),
        reimbursements=(CompensationInput("Reimb", Decimal("5")),),
    ))
    types = [ln.line_type for ln in r.lines]
    assert types == ["base", "allowance", "bonus", "bonus", "deduction", "reimbursement"]


def test_net_pay_money_redacts():
    r = calculate_payslip(_input())
    assert "100000" not in str(r.net_pay_money())
    assert "REDACTED" in str(r.net_pay_money())
