"""Dashboard expiring-document panel: presence, sorting, and role gating."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.employees.models import Employee, PayBasis
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


@pytest.fixture
def acme_with_docs(db):  # type: ignore[no-untyped-def]
    company = Company.objects.create(
        slug="exp-acme", name="Expiry Acme", country="PK", currency="PKR",
    )
    admin = User.objects.create_user(
        email="exp-admin@acme.local", password="x",
        role=Role.COMPANY_ADMIN, company=company,
    )
    today = date.today()
    with tenant_context(company), user_context(admin):
        Employee.objects.create(
            company=company, first_name="Soon", last_name="Expires",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
            hire_date=date(2025, 1, 1),
            passport_expiry=today + timedelta(days=10),
        )
        Employee.objects.create(
            company=company, first_name="Past", last_name="Due",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
            hire_date=date(2025, 1, 1),
            visa_expiry=today - timedelta(days=3),
        )
        Employee.objects.create(
            company=company, first_name="Far", last_name="Out",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
            hire_date=date(2025, 1, 1),
            passport_expiry=today + timedelta(days=120),
        )
        # Inactive employee with an expiring passport must NOT appear.
        Employee.objects.create(
            company=company, first_name="In", last_name="Active",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
            hire_date=date(2025, 1, 1),
            passport_expiry=today + timedelta(days=5),
            is_active=False,
        )
    portal = User.objects.create_user(
        email="exp-portal@acme.local", password="x", role=Role.EMPLOYEE, company=company,
    )
    return {"company": company, "admin": admin, "portal": portal}


HOST = {"HTTP_HOST": "exp-acme.localhost"}


@pytest.mark.django_db
def test_panel_appears_for_admin(acme_with_docs) -> None:  # type: ignore[no-untyped-def]
    ctx = acme_with_docs
    client = Client()
    client.force_login(ctx["admin"])
    response = client.get("/", **HOST)
    assert response.status_code == 200
    body = response.content.decode()
    assert "Expiring identity documents" in body
    assert "Soon Expires" in body
    assert "Past Due" in body
    assert "Far Out" not in body
    assert "In Active" not in body


@pytest.mark.django_db
def test_panel_shows_overdue_count_for_expired(acme_with_docs) -> None:  # type: ignore[no-untyped-def]
    ctx = acme_with_docs
    client = Client()
    client.force_login(ctx["admin"])
    response = client.get("/", **HOST)
    body = response.content.decode()
    assert "Expired" in body
    # The "Past Due" row should be 3 days ago.
    assert "Expired 3 days ago" in body


@pytest.mark.django_db
def test_panel_absent_for_employee(acme_with_docs) -> None:  # type: ignore[no-untyped-def]
    ctx = acme_with_docs
    client = Client()
    client.force_login(ctx["portal"])
    response = client.get("/", **HOST)
    # Employee is redirected to /payroll/my/; that page must NOT show the admin panel.
    assert response.status_code == 302
    follow = client.get(response.url, **HOST)
    assert "Expiring identity documents" not in follow.content.decode()


@pytest.mark.django_db
def test_panel_empty_when_no_expiring_docs(db) -> None:  # type: ignore[no-untyped-def]
    company = Company.objects.create(
        slug="exp-clean", name="x", country="PK", currency="PKR",
    )
    admin = User.objects.create_user(
        email="clean@acme.local", password="x", role=Role.COMPANY_ADMIN, company=company,
    )
    client = Client()
    client.force_login(admin)
    response = client.get("/", HTTP_HOST="exp-clean.localhost")
    assert response.status_code == 200
    assert "Expiring identity documents" not in response.content.decode()
