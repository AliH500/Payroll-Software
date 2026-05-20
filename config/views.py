"""Root home view with dashboard counters for tenant users."""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import redirect
from django.views.generic import TemplateView

EXPIRY_WINDOW_DAYS = 60


class HomeView(TemplateView):
    template_name = "home.html"

    def dispatch(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return redirect("login")
        from apps.accounts.models import Role
        if request.user.role == Role.EMPLOYEE:
            return redirect("payroll:my_payslip_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        user = self.request.user
        if tenant and user.is_authenticated:
            # Late-import to avoid app-registry issues at module import.
            from apps.employees.models import Employee
            from apps.payroll.models import PayPeriod, Payslip, PeriodStatus

            ctx["active_employees"] = Employee.objects.filter(is_active=True).count()
            ctx["open_periods"] = PayPeriod.objects.filter(status=PeriodStatus.OPEN).count()
            ctx["payslips_this_year"] = Payslip.objects.filter(
                period__year=date.today().year,
            ).count()
            ctx["expiring_docs"] = self._expiring_docs()
        return ctx

    def _expiring_docs(self) -> list[dict[str, object]]:
        """Active employees with passport or visa expiring within EXPIRY_WINDOW_DAYS."""
        from apps.employees.models import Employee

        today = date.today()
        cutoff = today + timedelta(days=EXPIRY_WINDOW_DAYS)
        candidates = Employee.objects.filter(is_active=True).filter(
            Q(passport_expiry__lte=cutoff) | Q(visa_expiry__lte=cutoff),
        )
        rows: list[dict[str, object]] = []
        for emp in candidates:
            if emp.passport_expiry and emp.passport_expiry <= cutoff:
                days_remaining = (emp.passport_expiry - today).days
                rows.append({
                    "employee": emp,
                    "doc_type": "Passport",
                    "expiry": emp.passport_expiry,
                    "days_remaining": days_remaining,
                    "days_overdue": -days_remaining if days_remaining < 0 else 0,
                })
            if emp.visa_expiry and emp.visa_expiry <= cutoff:
                days_remaining = (emp.visa_expiry - today).days
                rows.append({
                    "employee": emp,
                    "doc_type": "Visa",
                    "expiry": emp.visa_expiry,
                    "days_remaining": days_remaining,
                    "days_overdue": -days_remaining if days_remaining < 0 else 0,
                })
        rows.sort(key=lambda r: r["days_remaining"])  # type: ignore[arg-type,return-value]
        return rows
