"""End-to-end test that Postgres RLS blocks cross-tenant reads at the DB layer.

This is the third layer of multi-tenant defense; the test verifies the policy
is actually enforced when the connection is configured for a specific tenant.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import connection

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.employees.models import Employee, PayBasis
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


@pytest.fixture
def two_tenants(db):  # type: ignore[no-untyped-def]
    acme = Company.objects.create(slug="rls-acme", name="RLS Acme", country="PK", currency="PKR")
    beta = Company.objects.create(slug="rls-beta", name="RLS Beta", country="ET", currency="ETB")
    alice = User.objects.create_user(
        email="rls-alice@acme.local", password="x", role=Role.COMPANY_ADMIN, company=acme,
    )
    bob = User.objects.create_user(
        email="rls-bob@beta.local", password="x", role=Role.COMPANY_ADMIN, company=beta,
    )
    with tenant_context(acme), user_context(alice):
        Employee.objects.create(
            company=acme, first_name="Acme", last_name="One",
            pay_basis=PayBasis.FIXED, base_salary="50000", hire_date=date(2025, 1, 1),
        )
    with tenant_context(beta), user_context(bob):
        Employee.objects.create(
            company=beta, first_name="Beta", last_name="One",
            pay_basis=PayBasis.FIXED, base_salary="40000", hire_date=date(2025, 1, 1),
        )
    return acme, beta


def _set_rls_session(tenant_id: int | None, *, super_admin: bool) -> None:
    tid = str(tenant_id) if tenant_id is not None else "0"
    is_super = "true" if super_admin else "false"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_tenant_id', %s, false), "
            "set_config('app.is_super_admin', %s, false)",
            [tid, is_super],
        )


def _company_ids_visible() -> set[int]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT company_id FROM employees_employee")
        return {row[0] for row in cursor.fetchall()}


@pytest.mark.django_db
def test_rls_isolates_employees_per_tenant(two_tenants) -> None:  # type: ignore[no-untyped-def]
    acme, beta = two_tenants
    try:
        _set_rls_session(acme.pk, super_admin=False)
        assert _company_ids_visible() == {acme.pk}

        _set_rls_session(beta.pk, super_admin=False)
        assert _company_ids_visible() == {beta.pk}
    finally:
        _set_rls_session(None, super_admin=True)


@pytest.mark.django_db
def test_rls_unknown_tenant_sees_nothing(two_tenants) -> None:  # type: ignore[no-untyped-def]
    try:
        _set_rls_session(999_999, super_admin=False)
        assert _company_ids_visible() == set()
    finally:
        _set_rls_session(None, super_admin=True)


@pytest.mark.django_db
def test_rls_super_admin_sees_all(two_tenants) -> None:  # type: ignore[no-untyped-def]
    acme, beta = two_tenants
    _set_rls_session(None, super_admin=True)
    visible = _company_ids_visible()
    assert acme.pk in visible
    assert beta.pk in visible
