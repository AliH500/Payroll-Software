"""Seed a super-admin, one tenant Company, one tenant admin, and a few sample employees."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.employees.models import Employee, PayBasis
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Create a super-admin, one tenant Company, one tenant admin, and sample employees."

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        super_admin, created_su = User.objects.get_or_create(
            email="ali@platform.local",
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "role": Role.SUPER_ADMIN,
            },
        )
        if created_su:
            super_admin.set_password("demo-platform-2026")
            super_admin.save()

        acme, _ = Company.objects.get_or_create(
            slug="acme",
            defaults={"name": "Acme Imports", "country": "PK", "currency": "PKR"},
        )
        beta, _ = Company.objects.get_or_create(
            slug="beta",
            defaults={"name": "Beta Exports", "country": "ET", "currency": "ETB"},
        )

        alice, created_alice = User.objects.get_or_create(
            email="alice@acme.local",
            defaults={
                "is_staff": False,
                "is_superuser": False,
                "role": Role.COMPANY_ADMIN,
                "company": acme,
            },
        )
        if created_alice:
            alice.set_password("demo-acme-2026")
            alice.save()

        bob, created_bob = User.objects.get_or_create(
            email="bob@beta.local",
            defaults={
                "is_staff": False,
                "is_superuser": False,
                "role": Role.COMPANY_ADMIN,
                "company": beta,
            },
        )
        if created_bob:
            bob.set_password("demo-beta-2026")
            bob.save()

        def _seed_employees(tenant: Company, owner: User, roster: list) -> None:
            with tenant_context(tenant), user_context(owner):
                for first, last, basis, rate in roster:
                    if Employee.objects.filter(  # type: ignore[misc]
                        first_name=first, last_name=last
                    ).exists():
                        continue
                    payload = {
                        "company": tenant,
                        "first_name": first,
                        "last_name": last,
                        "pay_basis": basis,
                        "hire_date": date(2025, 1, 1),
                    }
                    if basis == PayBasis.FIXED:
                        payload["base_salary"] = rate
                    elif basis == PayBasis.HOURLY:
                        payload["hourly_rate"] = rate
                    else:
                        payload["unit_rate"] = rate
                    Employee.objects.create(**payload)  # type: ignore[misc]

        _seed_employees(acme, alice, [
            ("Mira", "Iqbal", PayBasis.FIXED, Decimal("85000")),
            ("Sami", "Khan", PayBasis.HOURLY, Decimal("450")),
            ("Bilal", "Ahmed", PayBasis.UNIT, Decimal("12.50")),
            ("Hira", "Sheikh", PayBasis.FIXED, Decimal("110000")),
        ])
        _seed_employees(beta, bob, [
            ("Tigist", "Bekele", PayBasis.FIXED, Decimal("18000")),
            ("Yonas", "Tesfaye", PayBasis.HOURLY, Decimal("90")),
            ("Senait", "Hailu", PayBasis.UNIT, Decimal("3.50")),
        ])

        # Open the current month's pay period and run payroll so the dashboard
        # has something to show. We skip employees whose hourly/unit inputs are
        # missing, which keeps the seed idempotent without prompting.
        from datetime import date as _today_fn
        from decimal import Decimal as _D

        from apps.compensation.models import Bonus, Deduction
        from apps.payroll.models import PayPeriod
        from apps.payroll.services import run_payroll_for_period

        today = _today_fn.today()
        period, _ = PayPeriod.all_tenants.get_or_create(  # type: ignore[misc]
            company=acme, year=today.year, month=today.month,
        )

        # Add a sample bonus + deduction for one of the fixed-salary employees.
        with tenant_context(acme), user_context(alice):
            mira = Employee.objects.filter(  # type: ignore[misc]
                first_name="Mira", last_name="Iqbal",
            ).first()
            if mira and not Bonus.objects.filter(employee=mira, period=period).exists():
                Bonus.objects.create(
                    company=acme, employee=mira, period=period,
                    description="Performance bonus", amount=_D("5000"),
                )
            if mira and not Deduction.objects.filter(employee=mira, period=period).exists():
                Deduction.objects.create(
                    company=acme, employee=mira, period=period,
                    description="Provident fund", amount=_D("3500"),
                )

            # Run payroll. Hourly/unit employees without hours/units recorded are skipped.
            hours = {}
            units = {}
            sami = Employee.objects.filter(first_name="Sami").first()  # type: ignore[misc]
            bilal = Employee.objects.filter(first_name="Bilal").first()  # type: ignore[misc]
            if sami:
                hours[sami.pk] = _D("168")
            if bilal:
                units[bilal.pk] = _D("3200")
            run_payroll_for_period(period, hours_by_employee=hours, units_by_employee=units)

        # Link a sample employee on each tenant to a self-service portal user.
        def _link_employee_user(
            tenant: Company, first: str, last: str, email: str, password: str,
        ) -> None:
            employee = Employee.all_tenants.filter(  # tenant-bypass-allowed: seed command
                company=tenant, first_name=first, last_name=last,
            ).first()
            if employee is None:
                return
            if employee.user_id is not None:
                return
            portal_user, created_portal = User.objects.get_or_create(
                email=email,
                defaults={
                    "is_staff": False,
                    "is_superuser": False,
                    "role": Role.EMPLOYEE,
                    "company": tenant,
                },
            )
            if created_portal:
                portal_user.set_password(password)
                portal_user.save()
            employee.user = portal_user
            employee.save(update_fields=["user", "updated_at"])

        _link_employee_user(acme, "Mira", "Iqbal", "mira@acme.local", "demo-employee-2026")
        _link_employee_user(beta, "Tigist", "Bekele", "tigist@beta.local", "demo-employee-2026")

        # tenant-bypass-allowed: seed command
        acme_count = Employee.all_tenants.filter(company=acme).count()
        # tenant-bypass-allowed: seed command
        beta_count = Employee.all_tenants.filter(company=beta).count()
        self.stdout.write(self.style.SUCCESS("Demo seed applied."))
        self.stdout.write("Super-admin: ali@platform.local / demo-platform-2026")
        self.stdout.write("  -> visit http://localhost:8000")
        self.stdout.write("Acme admin (PKR):  alice@acme.local / demo-acme-2026")
        self.stdout.write(f"  -> visit http://acme.localhost:8000 ({acme_count} employees)")
        self.stdout.write("Beta admin (ETB):  bob@beta.local / demo-beta-2026")
        self.stdout.write(f"  -> visit http://beta.localhost:8000 ({beta_count} employees)")
        self.stdout.write("Acme employee (PKR): mira@acme.local / demo-employee-2026")
        self.stdout.write("  -> visit http://acme.localhost:8000 (employee self-service)")
        self.stdout.write("Beta employee (ETB): tigist@beta.local / demo-employee-2026")
        self.stdout.write("  -> visit http://beta.localhost:8000 (employee self-service)")
