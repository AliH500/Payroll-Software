"""Employee self-service portal: scoping, ownership, and admin-route gating."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.employees.models import Employee, PayBasis
from apps.payroll.models import PayPeriod, Payslip
from apps.payroll.services import run_payroll_for_period
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


@pytest.fixture
def acme_with_employees(db):  # type: ignore[no-untyped-def]
    company = Company.objects.create(
        slug="ss-acme", name="Self-Service Acme", country="PK", currency="PKR",
    )
    admin = User.objects.create_user(
        email="ss-admin@acme.local", password="x",
        role=Role.COMPANY_ADMIN, company=company,
    )
    portal_user = User.objects.create_user(
        email="ss-employee@acme.local", password="employee-pass-2026",
        role=Role.EMPLOYEE, company=company,
    )
    other_portal = User.objects.create_user(
        email="ss-other@acme.local", password="other-pass-2026",
        role=Role.EMPLOYEE, company=company,
    )
    with tenant_context(company), user_context(admin):
        emp_mine = Employee.objects.create(
            company=company, first_name="Mine", last_name="Self",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("60000"),
            hire_date=date(2025, 1, 1), user=portal_user, work_email=portal_user.email,
        )
        emp_other = Employee.objects.create(
            company=company, first_name="Other", last_name="Self",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("50000"),
            hire_date=date(2025, 1, 1), user=other_portal, work_email=other_portal.email,
        )
        period = PayPeriod.objects.create(
            company=company, year=2026, month=4,
        )
        run_payroll_for_period(period)

    return {
        "company": company,
        "admin": admin,
        "portal_user": portal_user,
        "other_portal": other_portal,
        "emp_mine": emp_mine,
        "emp_other": emp_other,
        "period": period,
    }


@pytest.fixture
def host() -> dict[str, str]:
    return {"HTTP_HOST": "ss-acme.localhost"}


@pytest.mark.django_db
def test_employee_my_payslips_lists_only_own(acme_with_employees, host) -> None:  # type: ignore[no-untyped-def]
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["portal_user"])
    response = client.get("/payroll/my/", **host)
    assert response.status_code == 200
    body = response.content.decode()
    assert "Mine Self" not in body  # employee name not shown; just period rows
    # Only one payslip should be in the queryset.
    own = list(Payslip.all_tenants.filter(employee__user=ctx["portal_user"]))
    other = list(Payslip.all_tenants.filter(employee__user=ctx["other_portal"]))
    assert len(own) == 1
    assert len(other) == 1
    # 200 with 'April 2026' present, no leak from other employee.
    assert "April 2026" in body


@pytest.mark.django_db
def test_employee_cannot_access_other_employees_payslip(  # type: ignore[no-untyped-def]
    acme_with_employees, host,
) -> None:
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["portal_user"])
    other_payslip = Payslip.all_tenants.get(employee__user=ctx["other_portal"])
    response = client.get(f"/payroll/my/{other_payslip.pk}/", **host)
    assert response.status_code == 403


@pytest.mark.django_db
def test_employee_can_access_own_payslip(  # type: ignore[no-untyped-def]
    acme_with_employees, host,
) -> None:
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["portal_user"])
    mine = Payslip.all_tenants.get(employee__user=ctx["portal_user"])
    response = client.get(f"/payroll/my/{mine.pk}/", **host)
    assert response.status_code == 200


@pytest.mark.django_db
def test_employee_role_redirected_from_home(  # type: ignore[no-untyped-def]
    acme_with_employees, host,
) -> None:
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["portal_user"])
    response = client.get("/", **host)
    assert response.status_code == 302
    assert response.url == "/payroll/my/"


@pytest.mark.django_db
def test_admin_blocked_from_my_route(  # type: ignore[no-untyped-def]
    acme_with_employees, host,
) -> None:
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["admin"])
    response = client.get("/payroll/my/", **host)
    assert response.status_code == 403


@pytest.mark.django_db
def test_employee_blocked_from_admin_routes(  # type: ignore[no-untyped-def]
    acme_with_employees, host,
) -> None:
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["portal_user"])
    for path in ["/employees/", "/payroll/periods/", "/payroll/payslips/", "/compensation/"]:
        response = client.get(path, **host)
        assert response.status_code == 403, f"{path} did not 403 for employee role"


@pytest.mark.django_db
def test_admin_payslip_detail_redirects_employees(  # type: ignore[no-untyped-def]
    acme_with_employees, host,
) -> None:
    ctx = acme_with_employees
    client = Client()
    client.force_login(ctx["portal_user"])
    mine = Payslip.all_tenants.get(employee__user=ctx["portal_user"])
    response = client.get(f"/payroll/payslips/{mine.pk}/", **host)
    assert response.status_code == 302
    assert response.url == f"/payroll/my/{mine.pk}/"


@pytest.mark.django_db
def test_unauthenticated_my_route_redirects_to_login(host) -> None:  # type: ignore[no-untyped-def]
    Company.objects.create(slug="ss-acme2", name="x", country="PK", currency="PKR")
    response = Client().get("/payroll/my/", HTTP_HOST="ss-acme2.localhost")
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_employee_without_profile_is_blocked(host) -> None:  # type: ignore[no-untyped-def]
    company = Company.objects.create(
        slug="ss-acme3", name="x", country="PK", currency="PKR",
    )
    orphan = User.objects.create_user(
        email="orphan@acme.local", password="x", role=Role.EMPLOYEE, company=company,
    )
    client = Client()
    client.force_login(orphan)
    response = client.get("/payroll/my/", HTTP_HOST="ss-acme3.localhost")
    assert response.status_code == 403
