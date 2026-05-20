"""Root home view with dashboard counters for tenant users."""

from __future__ import annotations

from datetime import date

from django.shortcuts import redirect
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "home.html"

    def dispatch(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return redirect("login")
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
        return ctx
