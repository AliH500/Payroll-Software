"""Attendance CSV import: maps rows to employees by employee_code."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.attendance.csv_import import import_attendance
from apps.attendance.models import AttendanceRecord, AttendanceSheet
from apps.employees.models import Employee, PayBasis
from apps.payroll.models import PayPeriod
from apps.tenants.context import tenant_context
from apps.tenants.models import Company

HEADER = (
    "employee_code,days_present,days_late,days_total_absent,"
    "days_absent,days_leave"
)


@pytest.fixture
def setup(db):  # type: ignore[no-untyped-def]
    company = Company.objects.create(slug="att", name="Att Co", country="PK", currency="PKR")
    with tenant_context(company):
        emp = Employee.objects.create(
            company=company, employee_code="EMP-1", first_name="Ayesha", last_name="Khan",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("90000"), hire_date=date(2025, 1, 1),
        )
        period = PayPeriod.objects.create(company=company, year=2026, month=5)
        sheet = AttendanceSheet.objects.create(company=company, period=period)
    return company, emp, sheet


@pytest.mark.django_db
def test_happy_path_creates_record(setup):
    company, emp, sheet = setup
    csv = f"{HEADER}\nEMP-1,20,2,4,1,3\n"
    with tenant_context(company):
        outcomes = import_attendance(sheet, csv)
        record = AttendanceRecord.objects.get(sheet=sheet, employee=emp)
    assert outcomes[0].ok is True
    assert record.days_present == 20
    assert record.days_late == 2
    assert record.days_total_absent == 4
    assert record.days_absent == 1
    assert record.days_leave == 3


@pytest.mark.django_db
def test_reimport_updates_existing_record(setup):
    company, emp, sheet = setup
    with tenant_context(company):
        import_attendance(sheet, f"{HEADER}\nEMP-1,20,2,4,1,3\n")
        import_attendance(sheet, f"{HEADER}\nEMP-1,22,0,0,0,0\n")
        record = AttendanceRecord.objects.get(sheet=sheet, employee=emp)
        assert AttendanceRecord.objects.filter(sheet=sheet).count() == 1
    assert record.days_present == 22
    assert record.days_late == 0


@pytest.mark.django_db
def test_unknown_code_is_rejected(setup):
    company, _emp, sheet = setup
    with tenant_context(company):
        outcomes = import_attendance(sheet, f"{HEADER}\nGHOST-9,20,0,0,0,0\n")
    assert outcomes[0].ok is False
    assert "no employee with code" in outcomes[0].message


@pytest.mark.django_db
def test_duplicate_code_in_file_is_rejected(setup):
    company, _emp, sheet = setup
    csv = f"{HEADER}\nEMP-1,20,0,0,0,0\nEMP-1,18,0,0,0,0\n"
    with tenant_context(company):
        outcomes = import_attendance(sheet, csv)
    assert outcomes[0].ok is True
    assert outcomes[1].ok is False
    assert "duplicate" in outcomes[1].message.lower()


@pytest.mark.django_db
def test_negative_count_is_rejected(setup):
    company, _emp, sheet = setup
    with tenant_context(company):
        outcomes = import_attendance(sheet, f"{HEADER}\nEMP-1,-3,0,0,0,0\n")
    assert outcomes[0].ok is False
    assert "negative" in outcomes[0].message


@pytest.mark.django_db
def test_total_absent_mismatch_is_rejected(setup):
    company, _emp, sheet = setup
    # days_total_absent=5 but days_absent + days_leave = 1 + 3 = 4.
    with tenant_context(company):
        outcomes = import_attendance(sheet, f"{HEADER}\nEMP-1,20,0,5,1,3\n")
    assert outcomes[0].ok is False
    assert "days_total_absent" in outcomes[0].message


@pytest.mark.django_db
def test_other_company_code_is_not_mapped(setup):
    company, _emp, sheet = setup
    other = Company.objects.create(slug="att2", name="Att Two", country="ET", currency="ETB")
    with tenant_context(other):
        Employee.objects.create(
            company=other, employee_code="EMP-1", first_name="Beta", last_name="Worker",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("1"), hire_date=date(2025, 1, 1),
        )
    # The sheet belongs to `company`; EMP-1 exists in `other` but must not be reachable.
    with tenant_context(company):
        import_attendance(sheet, f"{HEADER}\nEMP-1,20,0,0,0,0\n")
        record = AttendanceRecord.objects.get(sheet=sheet, employee__employee_code="EMP-1")
    assert record.employee.company_id == company.pk


@pytest.mark.django_db
def test_missing_column_reports_error(setup):
    company, _emp, sheet = setup
    csv = "employee_code,days_present\nEMP-1,20\n"
    with tenant_context(company):
        outcomes = import_attendance(sheet, csv)
    assert outcomes[0].ok is False
    assert "Missing required column" in outcomes[0].message
