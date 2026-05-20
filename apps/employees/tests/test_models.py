from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.audit.models import AuditLogEntry
from apps.employees.models import Employee, PayBasis
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
            first_name="Bob",
            last_name="Khan",
            national_id="35202-1234567-8",
            pay_basis=PayBasis.FIXED,
            base_salary=Decimal("125000.00"),
            hire_date=date(2026, 1, 1),
        )
    fetched = Employee.all_tenants.get(pk=employee.pk)
    assert fetched.national_id == "35202-1234567-8"
    assert fetched.base_salary == Decimal("125000.00")


@pytest.mark.django_db
def test_pay_rate_resolves_by_basis(acme):
    with tenant_context(acme):
        fixed = Employee.objects.create(
            company=acme, first_name="A", last_name="A",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("100"),
            hire_date=date(2026, 1, 1),
        )
        hourly = Employee.objects.create(
            company=acme, first_name="B", last_name="B",
            pay_basis=PayBasis.HOURLY, hourly_rate=Decimal("50"),
            hire_date=date(2026, 1, 1),
        )
        unit = Employee.objects.create(
            company=acme, first_name="C", last_name="C",
            pay_basis=PayBasis.UNIT, unit_rate=Decimal("3.50"),
            hire_date=date(2026, 1, 1),
        )
    assert fixed.pay_rate == Decimal("100")
    assert hourly.pay_rate == Decimal("50")
    assert unit.pay_rate == Decimal("3.50")


@pytest.mark.django_db
def test_pay_rate_money_uses_company_currency(acme):
    with tenant_context(acme):
        e = Employee.objects.create(
            company=acme, first_name="X", last_name="Y",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("100"),
            hire_date=date(2026, 1, 1),
        )
    money = e.pay_rate_money()
    assert money is not None
    assert money.currency == "PKR"
    assert "100" not in str(money)  # redacted


@pytest.mark.django_db
def test_tenant_manager_scopes_employees(acme):
    other = Company.objects.create(slug="beta", name="Beta", country="ET", currency="ETB")
    with tenant_context(acme):
        Employee.objects.create(
            company=acme, first_name="Acme", last_name="Worker",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("100"),
            hire_date=date(2026, 1, 1),
        )
    with tenant_context(other):
        Employee.objects.create(
            company=other, first_name="Beta", last_name="Worker",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("100"),
            hire_date=date(2026, 1, 1),
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
            company=acme, first_name="Audit", last_name="Me",
            pay_basis=PayBasis.HOURLY, hourly_rate=Decimal("25"),
            hire_date=date(2026, 1, 1),
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
            company=acme, first_name="Bye", last_name="Felicia",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("100"),
            hire_date=date(2026, 1, 1),
        )
        pk = e.pk
        e.delete()
    actions = list(
        AuditLogEntry.objects.filter(
            target_model="employees.Employee", target_id=str(pk)
        ).values_list("action", flat=True)
    )
    assert "delete" in actions
