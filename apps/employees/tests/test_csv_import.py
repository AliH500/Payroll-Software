"""CSV import: employee_code is required and unique within a company."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.employees.csv_import import import_employees
from apps.employees.models import Employee
from apps.tenants.context import tenant_context
from apps.tenants.models import Company

HEADER = "employee_code,first_name,last_name,salary,hire_date"


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(slug="csv-acme", name="CSV Acme", country="PK", currency="PKR")


@pytest.mark.django_db
def test_imports_rows_with_codes(acme):
    csv = f"{HEADER}\nEMP-1,Ayesha,Khan,90000,2025-01-01\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert [o.ok for o in outcomes] == [True]
    emp = Employee.all_tenants.get(company=acme, employee_code="EMP-1")
    assert emp.full_name == "Ayesha Khan"
    assert emp.salary == Decimal("90000")


@pytest.mark.django_db
def test_imports_optional_allowances(acme):
    header = HEADER + ",conveyance_allowance,attendance_allowance,performance_bonus"
    csv = f"{header}\nEMP-2,Sana,Malik,80000,2025-01-01,4000,2000,1000\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
        emp = Employee.objects.get(employee_code="EMP-2")
    assert outcomes[0].ok is True
    assert emp.conveyance_allowance == Decimal("4000")
    assert emp.attendance_allowance == Decimal("2000")
    assert emp.performance_bonus == Decimal("1000")


@pytest.mark.django_db
def test_allowances_default_to_zero(acme):
    csv = f"{HEADER}\nEMP-3,Omar,Farooq,70000,2025-01-01\n"
    with tenant_context(acme):
        import_employees(acme, csv)
        emp = Employee.objects.get(employee_code="EMP-3")
    assert emp.conveyance_allowance == Decimal("0")
    assert emp.attendance_allowance == Decimal("0")
    assert emp.performance_bonus == Decimal("0")


@pytest.mark.django_db
def test_rejects_missing_salary(acme):
    header = "employee_code,first_name,last_name,salary,hire_date"
    csv = f"{header}\nEMP-1,Ayesha,Khan,,2025-01-01\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is False
    assert "salary is required" in outcomes[0].message


@pytest.mark.django_db
def test_rejects_missing_code(acme):
    csv = f"{HEADER}\n,Ayesha,Khan,90000,2025-01-01\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is False
    assert "employee_code is required" in outcomes[0].message
    assert Employee.all_tenants.filter(company=acme).count() == 0


@pytest.mark.django_db
def test_rejects_missing_code_column(acme):
    csv = "first_name,last_name,salary,hire_date\nA,B,1,2025-01-01\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is False
    assert "employee_code" in outcomes[0].message


@pytest.mark.django_db
def test_rejects_duplicate_code_in_file(acme):
    csv = (
        f"{HEADER}\n"
        "EMP-1,Ayesha,Khan,90000,2025-01-01\n"
        "EMP-1,Bilal,Ahmed,80000,2025-01-01\n"
    )
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is True
    assert outcomes[1].ok is False
    assert "duplicate" in outcomes[1].message.lower()


@pytest.mark.django_db
def test_rejects_code_already_in_db(acme):
    with tenant_context(acme):
        import_employees(acme, f"{HEADER}\nEMP-1,Ayesha,Khan,90000,2025-01-01\n")
        outcomes = import_employees(acme, f"{HEADER}\nEMP-1,Other,Person,1,2025-01-01\n")
    assert outcomes[0].ok is False
    assert "already exists" in outcomes[0].message
