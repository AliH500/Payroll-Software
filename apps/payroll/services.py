"""ORM-bound wrappers that orchestrate the pure calculator in services.payroll."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.compensation.models import Bonus, Deduction, ExpenseReimbursement
from apps.employees.models import Employee
from apps.payroll.models import PayPeriod, Payslip, PayslipLine
from services.payroll.calculator import (
    CompensationInput,
    PayrollInput,
    calculate_payslip,
)


def _comp_list(qs) -> tuple[CompensationInput, ...]:  # type: ignore[no-untyped-def]
    return tuple(CompensationInput(description=c.description, amount=c.amount) for c in qs)


@transaction.atomic
def run_payroll_for_period(
    period: PayPeriod,
    *,
    hours_by_employee: dict[int, Decimal] | None = None,
    units_by_employee: dict[int, Decimal] | None = None,
) -> list[Payslip]:
    """Create Payslip rows for every active employee in the period's tenant.

    Existing payslips for the period are deleted and recreated, so re-running is safe.
    """
    hours_by_employee = hours_by_employee or {}
    units_by_employee = units_by_employee or {}

    Payslip.all_tenants.filter(period=period).delete()  # type: ignore[misc]

    employees = list(
        Employee.all_tenants.filter(company=period.company, is_active=True)  # type: ignore[misc]
    )
    created: list[Payslip] = []
    for emp in employees:
        bonuses = Bonus.all_tenants.filter(employee=emp, period=period)  # type: ignore[misc]
        deductions = Deduction.all_tenants.filter(employee=emp, period=period)  # type: ignore[misc]
        reimbursements = ExpenseReimbursement.all_tenants.filter(  # type: ignore[misc]
            employee=emp, period=period,
        )

        input_ = PayrollInput(
            pay_basis=emp.pay_basis,
            base_salary=emp.base_salary,
            hourly_rate=emp.hourly_rate,
            unit_rate=emp.unit_rate,
            hours_worked=hours_by_employee.get(emp.pk),
            units_processed=units_by_employee.get(emp.pk),
            bonuses=_comp_list(bonuses),
            deductions=_comp_list(deductions),
            reimbursements=_comp_list(reimbursements),
            currency=period.company.currency,
        )
        try:
            result = calculate_payslip(input_)
        except ValueError:
            # Skip employees with insufficient inputs (e.g., hourly with no hours entered).
            continue

        payslip = Payslip.objects.create(
            company=period.company,
            employee=emp,
            period=period,
            hours_worked=input_.hours_worked,
            units_processed=input_.units_processed,
            base_pay=result.base_pay,
            bonuses_total=result.bonuses_total,
            deductions_total=result.deductions_total,
            reimbursements_total=result.reimbursements_total,
            net_pay=result.net_pay,
            currency=result.currency,
        )
        PayslipLine.objects.bulk_create([
            PayslipLine(
                payslip=payslip,
                line_type=ln.line_type,
                description=ln.description,
                amount=ln.amount,
            )
            for ln in result.lines
        ])
        created.append(payslip)
    return created
