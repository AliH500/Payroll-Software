"""ORM-bound wrappers that orchestrate the pure calculator in services.payroll."""

from __future__ import annotations

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
def run_payroll_for_period(period: PayPeriod) -> list[Payslip]:
    """Create Payslip rows for every active employee in the period's tenant.

    Existing payslips for the period are deleted and recreated, so re-running is safe.
    """
    # tenant-bypass-allowed: payroll run is invoked from views that already gate by tenant
    Payslip.all_tenants.filter(period=period).delete()  # type: ignore[misc]

    employees = list(
        # tenant-bypass-allowed: payroll run is invoked from views that already gate by tenant
        Employee.all_tenants.filter(company=period.company, is_active=True)  # type: ignore[misc]
    )
    created: list[Payslip] = []
    for emp in employees:
        # tenant-bypass-allowed: payroll run is invoked from views that already gate by tenant
        bonuses = Bonus.all_tenants.filter(employee=emp, period=period)  # type: ignore[misc]
        # tenant-bypass-allowed: payroll run is invoked from views that already gate by tenant
        deductions = Deduction.all_tenants.filter(employee=emp, period=period)  # type: ignore[misc]
        # tenant-bypass-allowed: payroll run is invoked from views that already gate by tenant
        reimbursements = ExpenseReimbursement.all_tenants.filter(  # type: ignore[misc]
            employee=emp, period=period,
        )

        input_ = PayrollInput(
            salary=emp.salary,
            conveyance_allowance=emp.conveyance_allowance,
            attendance_allowance=emp.attendance_allowance,
            performance_bonus=emp.performance_bonus,
            bonuses=_comp_list(bonuses),
            deductions=_comp_list(deductions),
            reimbursements=_comp_list(reimbursements),
            currency=period.company.currency,
        )
        result = calculate_payslip(input_)

        payslip = Payslip.objects.create(
            company=period.company,
            employee=emp,
            period=period,
            base_pay=result.base_pay,
            allowances_total=result.allowances_total,
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
