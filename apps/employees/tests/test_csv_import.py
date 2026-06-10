"""CSV import: employee_code is required and unique within a company."""

from __future__ import annotations

import pytest

from apps.employees.csv_import import import_employees
from apps.employees.models import Employee
from apps.tenants.context import tenant_context
from apps.tenants.models import Company

HEADER = "employee_code,first_name,last_name,pay_basis,hire_date,base_salary"


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(slug="csv-acme", name="CSV Acme", country="PK", currency="PKR")


@pytest.mark.django_db
def test_imports_rows_with_codes(acme):
    csv = f"{HEADER}\nEMP-1,Ayesha,Khan,fixed,2025-01-01,90000\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert [o.ok for o in outcomes] == [True]
    emp = Employee.all_tenants.get(company=acme, employee_code="EMP-1")
    assert emp.full_name == "Ayesha Khan"


@pytest.mark.django_db
def test_rejects_missing_code(acme):
    csv = f"{HEADER}\n,Ayesha,Khan,fixed,2025-01-01,90000\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is False
    assert "employee_code is required" in outcomes[0].message
    assert Employee.all_tenants.filter(company=acme).count() == 0


@pytest.mark.django_db
def test_rejects_missing_code_column(acme):
    csv = "first_name,last_name,pay_basis,hire_date,base_salary\nA,B,fixed,2025-01-01,1\n"
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is False
    assert "employee_code" in outcomes[0].message


@pytest.mark.django_db
def test_rejects_duplicate_code_in_file(acme):
    csv = (
        f"{HEADER}\n"
        "EMP-1,Ayesha,Khan,fixed,2025-01-01,90000\n"
        "EMP-1,Bilal,Ahmed,fixed,2025-01-01,80000\n"
    )
    with tenant_context(acme):
        outcomes = import_employees(acme, csv)
    assert outcomes[0].ok is True
    assert outcomes[1].ok is False
    assert "duplicate" in outcomes[1].message.lower()


@pytest.mark.django_db
def test_rejects_code_already_in_db(acme):
    with tenant_context(acme):
        import_employees(acme, f"{HEADER}\nEMP-1,Ayesha,Khan,fixed,2025-01-01,90000\n")
        outcomes = import_employees(acme, f"{HEADER}\nEMP-1,Other,Person,fixed,2025-01-01,1\n")
    assert outcomes[0].ok is False
    assert "already exists" in outcomes[0].message
