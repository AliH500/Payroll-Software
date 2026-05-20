"""create_portal_account_view: links an Employee to a fresh User row."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.employees.models import Employee, PayBasis
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


@pytest.fixture
def acme_admin_and_employee(db):  # type: ignore[no-untyped-def]
    company = Company.objects.create(
        slug="pa-acme", name="Portal-Account Acme", country="PK", currency="PKR",
    )
    admin = User.objects.create_user(
        email="pa-admin@acme.local", password="x",
        role=Role.COMPANY_ADMIN, company=company,
    )
    with tenant_context(company), user_context(admin):
        emp = Employee.objects.create(
            company=company, first_name="Sara", last_name="Khan",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("70000"),
            hire_date=date(2025, 1, 1), work_email="sara@acme.local",
        )
        emp_no_email = Employee.objects.create(
            company=company, first_name="No", last_name="Email",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
            hire_date=date(2025, 1, 1),
        )
    viewer = User.objects.create_user(
        email="pa-viewer@acme.local", password="x", role=Role.VIEWER, company=company,
    )
    return {
        "company": company, "admin": admin, "viewer": viewer,
        "emp": emp, "emp_no_email": emp_no_email,
    }


HOST = {"HTTP_HOST": "pa-acme.localhost"}


@pytest.mark.django_db
def test_admin_can_create_portal_account(acme_admin_and_employee) -> None:  # type: ignore[no-untyped-def]
    ctx = acme_admin_and_employee
    client = Client()
    client.force_login(ctx["admin"])
    response = client.post(
        f"/employees/{ctx['emp'].pk}/create-portal-account/", **HOST,
    )
    assert response.status_code == 302
    new_user = User.objects.get(email="sara@acme.local")
    assert new_user.role == Role.EMPLOYEE
    assert new_user.company_id == ctx["company"].pk
    assert not new_user.has_usable_password()  # forces password reset
    ctx["emp"].refresh_from_db()
    assert ctx["emp"].user_id == new_user.pk


@pytest.mark.django_db
def test_create_portal_account_idempotent_on_repeat(  # type: ignore[no-untyped-def]
    acme_admin_and_employee,
) -> None:
    ctx = acme_admin_and_employee
    client = Client()
    client.force_login(ctx["admin"])
    first = client.post(f"/employees/{ctx['emp'].pk}/create-portal-account/", **HOST)
    assert first.status_code == 302
    user_count_before = User.objects.count()
    second = client.post(f"/employees/{ctx['emp'].pk}/create-portal-account/", **HOST)
    assert second.status_code == 302
    assert User.objects.count() == user_count_before  # no duplicate


@pytest.mark.django_db
def test_create_portal_account_blocks_employees_without_email(  # type: ignore[no-untyped-def]
    acme_admin_and_employee,
) -> None:
    ctx = acme_admin_and_employee
    client = Client()
    client.force_login(ctx["admin"])
    response = client.post(
        f"/employees/{ctx['emp_no_email'].pk}/create-portal-account/", **HOST,
    )
    assert response.status_code == 302  # redirect with error
    ctx["emp_no_email"].refresh_from_db()
    assert ctx["emp_no_email"].user_id is None


@pytest.mark.django_db
def test_viewer_role_cannot_create_portal_account(  # type: ignore[no-untyped-def]
    acme_admin_and_employee,
) -> None:
    ctx = acme_admin_and_employee
    client = Client()
    client.force_login(ctx["viewer"])
    response = client.post(
        f"/employees/{ctx['emp'].pk}/create-portal-account/", **HOST,
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_get_request_rejected(acme_admin_and_employee) -> None:  # type: ignore[no-untyped-def]
    ctx = acme_admin_and_employee
    client = Client()
    client.force_login(ctx["admin"])
    response = client.get(
        f"/employees/{ctx['emp'].pk}/create-portal-account/", **HOST,
    )
    assert response.status_code == 405  # require_POST
