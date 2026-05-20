from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
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
        password="strong-password-123",
        company=acme,
        role=Role.COMPANY_ADMIN,
    )


@pytest.fixture
def super_admin(db) -> User:
    return User.objects.create_superuser(
        email="ali@platform.local",
        password="platform-pass-456",
    )


@pytest.mark.django_db
class TestEmployeeListView:
    def test_anonymous_is_redirected_to_login(self, client):
        resp = client.get(reverse("employees:list"), HTTP_HOST="acme.localhost")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_authenticated_tenant_user_sees_list(self, client, acme, alice):
        client.force_login(alice)
        with tenant_context(acme):
            Employee.objects.create(
                company=acme, first_name="Eve", last_name="Hassan",
                pay_basis=PayBasis.FIXED, base_salary=Decimal("100"),
                hire_date=date(2026, 1, 1),
            )
        resp = client.get(reverse("employees:list"), HTTP_HOST="acme.localhost")
        assert resp.status_code == 200
        assert b"Hassan" in resp.content

    def test_root_domain_returns_403(self, client, alice):
        client.force_login(alice)
        resp = client.get(reverse("employees:list"), HTTP_HOST="localhost")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestEmployeeCreateView:
    def test_create_employee(self, client, acme, alice):
        client.force_login(alice)
        resp = client.post(
            reverse("employees:create"),
            {
                "first_name": "Mira",
                "last_name": "Iqbal",
                "work_email": "mira@acme.local",
                "phone": "+92-300-0000000",
                "national_id": "35202-9999999-9",
                "pay_basis": "fixed",
                "base_salary": "85000",
                "hire_date": "2026-05-01",
                "is_active": "on",
            },
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 302
        e = Employee.all_tenants.get(last_name="Iqbal")
        assert e.company == acme
        assert e.national_id == "35202-9999999-9"
        assert e.base_salary == Decimal("85000")

    def test_create_requires_rate_for_basis(self, client, acme, alice):
        client.force_login(alice)
        resp = client.post(
            reverse("employees:create"),
            {
                "first_name": "Bad",
                "last_name": "Form",
                "pay_basis": "hourly",
                # hourly_rate intentionally omitted
                "hire_date": "2026-05-01",
            },
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 200
        assert b"Required for the selected pay basis" in resp.content


@pytest.mark.django_db
class TestEmployeeUpdateAndDelete:
    @pytest.fixture
    def employee(self, acme):
        with tenant_context(acme):
            return Employee.objects.create(
                company=acme, first_name="Sam", last_name="K",
                pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
                hire_date=date(2026, 1, 1),
            )

    def test_update(self, client, acme, alice, employee):
        client.force_login(alice)
        resp = client.post(
            reverse("employees:update", args=[employee.pk]),
            {
                "first_name": "Samira",
                "last_name": "K",
                "pay_basis": "fixed",
                "base_salary": "60000",
                "hire_date": "2026-01-01",
                "is_active": "on",
            },
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 302
        employee.refresh_from_db()
        assert employee.first_name == "Samira"
        assert employee.base_salary == Decimal("60000")

    def test_delete(self, client, acme, alice, employee):
        client.force_login(alice)
        resp = client.post(
            reverse("employees:delete", args=[employee.pk]),
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 302
        assert not Employee.all_tenants.filter(pk=employee.pk).exists()
