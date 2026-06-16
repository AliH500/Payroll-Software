from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.audit.models import AuditLogEntry
from apps.employees.models import Employee
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(slug="acme", name="Acme", country="PK", currency="PKR")


@pytest.fixture
def alice(acme) -> User:
    return User.objects.create_user(
        email="alice@acme.local",
        password="x",
        company=acme,
        role=Role.COMPANY_ADMIN,
    )


@pytest.mark.django_db
def test_encrypted_field_round_trip(acme):
    with tenant_context(acme):
        employee = Employee.objects.create(
            company=acme,
            employee_code="EMP-1",
            first_name="Bob",
            last_name="Khan",
            national_id="35202-1234567-8",
            salary=Decimal("125000.00"),
            hire_date=date(2026, 1, 1),
        )
    fetched = Employee.all_tenants.get(pk=employee.pk)
    assert fetched.national_id == "35202-1234567-8"
    assert fetched.salary == Decimal("125000.00")


@pytest.mark.django_db
def test_allowances_default_to_zero(acme):
    with tenant_context(acme):
        employee = Employee.objects.create(
            company=acme, employee_code="EMP-1", first_name="A", last_name="A",
            salary=Decimal("100"), hire_date=date(2026, 1, 1),
        )
    fetched = Employee.all_tenants.get(pk=employee.pk)
    assert fetched.conveyance_allowance == Decimal("0")
    assert fetched.attendance_allowance == Decimal("0")
    assert fetched.performance_bonus == Decimal("0")


@pytest.mark.django_db
def test_salary_money_uses_company_currency(acme):
    with tenant_context(acme):
        e = Employee.objects.create(
            company=acme, employee_code="EMP-1", first_name="X", last_name="Y",
            salary=Decimal("100"), hire_date=date(2026, 1, 1),
        )
    money = e.salary_money()
    assert money.currency == "PKR"
    assert "100" not in str(money)  # redacted


@pytest.mark.django_db
def test_tenant_manager_scopes_employees(acme):
    other = Company.objects.create(slug="beta", name="Beta", country="ET", currency="ETB")
    with tenant_context(acme):
        Employee.objects.create(
            company=acme, employee_code="EMP-1", first_name="Acme", last_name="Worker",
            salary=Decimal("100"), hire_date=date(2026, 1, 1),
        )
    with tenant_context(other):
        Employee.objects.create(
            company=other, employee_code="EMP-1", first_name="Beta", last_name="Worker",
            salary=Decimal("100"), hire_date=date(2026, 1, 1),
        )

    with tenant_context(acme):
        names = sorted(e.last_name for e in Employee.objects.all())
        assert names == ["Worker"]
        assert all(e.company == acme for e in Employee.objects.all())

    assert Employee.all_tenants.count() == 2


@pytest.mark.django_db
def test_employee_save_emits_audit_entry(acme, alice):
    with tenant_context(acme), user_context(alice):
        employee = Employee.objects.create(
            company=acme, employee_code="EMP-1", first_name="Audit", last_name="Me",
            salary=Decimal("25000"), hire_date=date(2026, 1, 1),
        )
    entries = AuditLogEntry.objects.filter(
        target_model="employees.Employee", target_id=str(employee.pk)
    )
    assert entries.count() == 1
    entry = entries.first()
    assert entry is not None
    assert entry.actor == alice
    assert entry.action == "create"


@pytest.mark.django_db
def test_employee_delete_emits_audit_entry(acme, alice):
    with tenant_context(acme), user_context(alice):
        e = Employee.objects.create(
            company=acme, employee_code="EMP-1", first_name="Bye", last_name="Felicia",
            salary=Decimal("100"), hire_date=date(2026, 1, 1),
        )
        pk = e.pk
        e.delete()
    actions = list(
        AuditLogEntry.objects.filter(
            target_model="employees.Employee", target_id=str(pk)
        ).values_list("action", flat=True)
    )
    assert "delete" in actions
