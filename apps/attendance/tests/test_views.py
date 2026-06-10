"""Attendance sheet view: total working days, grid save, gating, closed-period lock."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.accounts.models import Role, User
from apps.attendance.models import AttendanceRecord, AttendanceSheet
from apps.employees.models import Employee, PayBasis
from apps.payroll.models import PayPeriod
from apps.tenants.context import tenant_context
from apps.tenants.models import Company

HOST = {"HTTP_HOST": "att-v.localhost"}


@pytest.fixture
def setup(db):  # type: ignore[no-untyped-def]
    company = Company.objects.create(slug="att-v", name="Att V", country="PK", currency="PKR")
    admin = User.objects.create_user(
        email="att-admin@x.local", password="x", role=Role.COMPANY_ADMIN, company=company,
    )
    portal = User.objects.create_user(
        email="att-emp@x.local", password="x", role=Role.EMPLOYEE, company=company,
    )
    with tenant_context(company):
        emp = Employee.objects.create(
            company=company, employee_code="EMP-1", first_name="Ayesha", last_name="Khan",
            pay_basis=PayBasis.FIXED, base_salary=Decimal("90000"), hire_date=date(2025, 1, 1),
        )
        period = PayPeriod.objects.create(company=company, year=2026, month=5)
    return {"company": company, "admin": admin, "portal": portal, "emp": emp, "period": period}


@pytest.mark.django_db
def test_saving_sheet_records_total_days_and_grid(setup):
    client = Client()
    client.force_login(setup["admin"])
    emp, period = setup["emp"], setup["period"]
    resp = client.post(f"/attendance/{period.pk}/", {
        "total_working_days": "22",
        f"present_{emp.pk}": "20",
        f"late_{emp.pk}": "2",
        f"absent_{emp.pk}": "0",
        f"awol_{emp.pk}": "0",
        f"leave_{emp.pk}": "2",
    }, **HOST)
    assert resp.status_code == 302
    sheet = AttendanceSheet.all_tenants.get(period=period)
    assert sheet.total_working_days == 22
    record = AttendanceRecord.all_tenants.get(sheet=sheet, employee=emp)
    assert record.days_present == 20
    assert record.days_leave == 2


@pytest.mark.django_db
def test_invalid_grid_value_does_not_save(setup):
    client = Client()
    client.force_login(setup["admin"])
    emp, period = setup["emp"], setup["period"]
    resp = client.post(f"/attendance/{period.pk}/", {
        "total_working_days": "22",
        f"present_{emp.pk}": "abc",
        f"late_{emp.pk}": "0",
        f"absent_{emp.pk}": "0",
        f"awol_{emp.pk}": "0",
        f"leave_{emp.pk}": "0",
    }, **HOST)
    assert resp.status_code == 200
    assert not AttendanceRecord.all_tenants.filter(employee=emp).exists()


@pytest.mark.django_db
def test_employee_role_is_blocked(setup):
    client = Client()
    client.force_login(setup["portal"])
    resp = client.get(f"/attendance/{setup['period'].pk}/", **HOST)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_closed_period_locks_attendance(setup):
    period = setup["period"]
    with tenant_context(setup["company"]):
        period.status = "closed"
        period.save()
    client = Client()
    client.force_login(setup["admin"])
    emp = setup["emp"]
    resp = client.post(f"/attendance/{period.pk}/", {
        "total_working_days": "22",
        f"present_{emp.pk}": "20",
        f"late_{emp.pk}": "0",
        f"absent_{emp.pk}": "0",
        f"awol_{emp.pk}": "0",
        f"leave_{emp.pk}": "0",
    }, **HOST)
    assert resp.status_code == 200
    assert not AttendanceRecord.all_tenants.filter(employee=emp).exists()


@pytest.mark.django_db
def test_total_working_days_over_31_is_rejected(setup):
    client = Client()
    client.force_login(setup["admin"])
    emp, period = setup["emp"], setup["period"]
    resp = client.post(f"/attendance/{period.pk}/", {
        "total_working_days": "35",
        f"present_{emp.pk}": "20",
        f"late_{emp.pk}": "0",
        f"absent_{emp.pk}": "0",
        f"awol_{emp.pk}": "0",
        f"leave_{emp.pk}": "0",
    }, **HOST)
    assert resp.status_code == 200
    assert not AttendanceSheet.all_tenants.filter(
        period=period, total_working_days=35,
    ).exists()
    assert not AttendanceRecord.all_tenants.filter(employee=emp).exists()


@pytest.mark.django_db
def test_period_list_access_control(setup):
    client = Client()
    # Tenant admin sees the list.
    client.force_login(setup["admin"])
    assert client.get("/attendance/", **HOST).status_code == 200
    # Employee self-service role is blocked.
    client.force_login(setup["portal"])
    assert client.get("/attendance/", **HOST).status_code == 403
    # Bare (non-tenant) host is blocked.
    client.force_login(setup["admin"])
    assert client.get("/attendance/", HTTP_HOST="localhost").status_code == 403


@pytest.mark.django_db
def test_template_download(setup):
    client = Client()
    client.force_login(setup["admin"])
    resp = client.get("/attendance/template.csv", **HOST)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert b"employee_code" in resp.content
    assert b"days_absent_without_leave" in resp.content
