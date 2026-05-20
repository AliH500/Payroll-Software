from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
)

from apps.payroll.forms import PayPeriodForm, RunPayrollForm
from apps.payroll.models import PayPeriod, Payslip
from apps.payroll.services import run_payroll_for_period


class _TenantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if getattr(request, "tenant", None) is None:
            raise PermissionDenied("This page is only available on a tenant subdomain.")
        return super().dispatch(request, *args, **kwargs)


class PayPeriodListView(_TenantRequiredMixin, ListView[PayPeriod]):
    model = PayPeriod
    template_name = "payroll/period_list.html"
    context_object_name = "periods"


class PayPeriodCreateView(_TenantRequiredMixin, CreateView[PayPeriod, PayPeriodForm]):
    model = PayPeriod
    form_class = PayPeriodForm
    template_name = "payroll/period_form.html"
    success_url = reverse_lazy("payroll:period_list")

    def form_valid(self, form: PayPeriodForm) -> HttpResponse:
        tenant = self.request.tenant  # type: ignore[attr-defined]
        year = form.cleaned_data["year"]
        month = form.cleaned_data["month"]
        if PayPeriod.all_tenants.filter(  # type: ignore[misc]
            company=tenant, year=year, month=month,
        ).exists():
            form.add_error(None, "A pay period for this month already exists.")
            return self.form_invalid(form)
        form.instance.company = tenant
        response = super().form_valid(form)
        messages.success(self.request, f"Opened {form.instance.label}.")
        return response


class PayPeriodDetailView(_TenantRequiredMixin, DetailView[PayPeriod]):
    model = PayPeriod
    template_name = "payroll/period_detail.html"
    context_object_name = "period"

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        ctx = super().get_context_data(**kwargs)
        ctx["payslips"] = Payslip.objects.filter(period=self.object).select_related("employee")
        return ctx


def run_payroll_view(request: HttpRequest, pk: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(f"/accounts/login/?next={request.path}")
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    period = get_object_or_404(PayPeriod, pk=pk)
    if period.is_closed:
        messages.error(request, "This period is closed.")
        return redirect("payroll:period_detail", pk=pk)

    if request.method == "POST":
        form = RunPayrollForm(request.POST, period=period)
        if form.is_valid():
            from apps.employees.models import Employee

            eligible = Employee.all_tenants.filter(  # type: ignore[misc]
                company=period.company, is_active=True,
            ).count()
            created = run_payroll_for_period(
                period,
                hours_by_employee=form.hours_by_employee(),
                units_by_employee=form.units_by_employee(),
            )
            skipped = eligible - len(created)
            messages.success(request, f"Generated {len(created)} payslip(s) for {period.label}.")
            if skipped:
                messages.warning(
                    request,
                    f"{skipped} employee(s) skipped (missing rate or attendance input).",
                )
            return redirect("payroll:period_detail", pk=pk)
    else:
        form = RunPayrollForm(period=period)

    return render(request, "payroll/run_payroll.html", {"period": period, "form": form})


def close_period_view(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("payroll:period_detail", pk=pk)
    if not request.user.is_authenticated:
        return redirect("login")
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    period = get_object_or_404(PayPeriod, pk=pk)
    period.status = "closed"
    period.closed_at = timezone.now()
    period.closed_by = request.user
    period.save()
    messages.success(request, f"{period.label} closed.")
    return redirect("payroll:period_detail", pk=pk)


class PayslipListView(_TenantRequiredMixin, ListView[Payslip]):
    model = Payslip
    template_name = "payroll/payslip_list.html"
    context_object_name = "payslips"
    paginate_by = 50

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Payslip.objects.select_related("employee", "period").all()


class PayslipDetailView(_TenantRequiredMixin, DetailView[Payslip]):
    model = Payslip
    template_name = "payroll/payslip_detail.html"
    context_object_name = "payslip"


class PeriodPayslipsPrintView(_TenantRequiredMixin, TemplateView):
    """One printable page with every payslip in a period."""
    template_name = "payroll/period_payslips_print.html"

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        ctx = super().get_context_data(**kwargs)
        period = get_object_or_404(PayPeriod, pk=self.kwargs["pk"])
        ctx["period"] = period
        ctx["payslips"] = list(
            Payslip.objects.filter(period=period).select_related("employee").prefetch_related("lines")
        )
        return ctx
