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

from apps.accounts.models import Role
from apps.payroll.forms import PayPeriodForm, RunPayrollForm
from apps.payroll.models import PayPeriod, Payslip
from apps.payroll.services import run_payroll_for_period


class _TenantRequiredMixin(LoginRequiredMixin):
    """Reject anonymous, non-tenant, and employee-role requests on admin payroll pages."""

    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if getattr(request, "tenant", None) is None:
            raise PermissionDenied("This page is only available on a tenant subdomain.")
        if request.user.role == Role.EMPLOYEE:
            raise PermissionDenied("This area is for company admins, not employee self-service.")
        return super().dispatch(request, *args, **kwargs)


class _EmployeeRequiredMixin(LoginRequiredMixin):
    """Restricts access to employee-self-service-only routes."""

    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if getattr(request, "tenant", None) is None:
            raise PermissionDenied("This page is only available on a tenant subdomain.")
        if request.user.role != Role.EMPLOYEE:
            raise PermissionDenied("Employee self-service only.")
        if not hasattr(request.user, "employee_profile") or request.user.employee_profile is None:
            raise PermissionDenied("No employee profile is linked to this account.")
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
    if request.user.role == Role.EMPLOYEE:
        raise PermissionDenied("Employee self-service cannot run payroll.")
    period = get_object_or_404(PayPeriod, pk=pk)
    if period.is_closed:
        messages.error(request, "This period is closed.")
        return redirect("payroll:period_detail", pk=pk)

    if request.method == "POST":
        form = RunPayrollForm(request.POST, period=period)
        if form.is_valid():
            from apps.employees.models import Employee

            # tenant-bypass-allowed: count is filtered by period.company on the same line
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
    if request.user.role == Role.EMPLOYEE:
        raise PermissionDenied("Employee self-service cannot close periods.")
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

    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if request.user.is_authenticated and request.user.role == Role.EMPLOYEE:
            return redirect("payroll:my_payslip_detail", pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)


class MyPayslipsView(_EmployeeRequiredMixin, ListView[Payslip]):
    """Self-service: an employee sees only their own payslips."""

    model = Payslip
    template_name = "payroll/my_payslips.html"
    context_object_name = "payslips"

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return (
            Payslip.objects.filter(employee__user=self.request.user)
            .select_related("employee", "period")
            .order_by("-period__year", "-period__month")
        )


class MyPayslipDetailView(_EmployeeRequiredMixin, DetailView[Payslip]):
    """Self-service payslip detail. 403s on any payslip the employee does not own."""

    model = Payslip
    template_name = "payroll/payslip_detail.html"
    context_object_name = "payslip"

    def get_object(self, queryset=None):  # type: ignore[no-untyped-def]
        payslip = super().get_object(queryset)
        if payslip.employee.user_id != self.request.user.pk:
            raise PermissionDenied("This payslip is not yours.")
        return payslip


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
