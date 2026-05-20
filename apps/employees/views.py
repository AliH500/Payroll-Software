from __future__ import annotations

import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.accounts.models import Role, User
from apps.employees.csv_import import csv_template_headers, import_employees
from apps.employees.forms import EmployeeForm
from apps.employees.models import Employee


class _TenantRequiredMixin(LoginRequiredMixin):
    """Reject anonymous, non-tenant, and employee-role requests."""

    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("This page is only available on a tenant subdomain.")
        if request.user.role == Role.EMPLOYEE:
            raise PermissionDenied("This area is for company admins, not employee self-service.")
        return super().dispatch(request, *args, **kwargs)


class EmployeeListView(_TenantRequiredMixin, ListView[Employee]):
    model = Employee
    template_name = "employees/list.html"
    context_object_name = "employees"
    paginate_by = 50


class EmployeeDetailView(_TenantRequiredMixin, DetailView[Employee]):
    model = Employee
    template_name = "employees/detail.html"
    context_object_name = "employee"


class EmployeeCreateView(_TenantRequiredMixin, CreateView[Employee, EmployeeForm]):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/form.html"
    success_url = reverse_lazy("employees:list")

    def get_form_kwargs(self):  # type: ignore[no-untyped-def]
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant  # type: ignore[attr-defined]
        return kwargs

    def form_valid(self, form: EmployeeForm) -> HttpResponse:
        form.instance.company = self.request.tenant  # type: ignore[attr-defined]
        response = super().form_valid(form)
        messages.success(self.request, f"Added {form.instance.full_name}.")
        return response


class EmployeeUpdateView(_TenantRequiredMixin, UpdateView[Employee, EmployeeForm]):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/form.html"
    success_url = reverse_lazy("employees:list")

    def get_form_kwargs(self):  # type: ignore[no-untyped-def]
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.tenant  # type: ignore[attr-defined]
        return kwargs

    def form_valid(self, form: EmployeeForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, f"Saved {form.instance.full_name}.")
        return response


class EmployeeDeleteView(_TenantRequiredMixin, DeleteView):  # type: ignore[type-arg]
    model = Employee
    template_name = "employees/confirm_delete.html"
    success_url = reverse_lazy("employees:list")

    def form_valid(self, form):  # type: ignore[no-untyped-def]
        name = self.object.full_name
        response = super().form_valid(form)
        messages.success(self.request, f"Removed {name}.")
        return response


@login_required
def csv_import_view(request: HttpRequest) -> HttpResponse:
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    if request.user.role == Role.EMPLOYEE:
        raise PermissionDenied("Employee self-service cannot import employees.")
    outcomes = None
    if request.method == "POST" and request.FILES.get("file"):
        uploaded = request.FILES["file"]
        outcomes = import_employees(request.tenant, uploaded.read())  # type: ignore[attr-defined]
        successes = sum(1 for o in outcomes if o.ok)
        failures = len(outcomes) - successes
        if successes:
            messages.success(request, f"Imported {successes} employee(s).")
        if failures:
            messages.warning(request, f"{failures} row(s) had errors; see report below.")
    return render(request, "employees/import.html", {
        "outcomes": outcomes,
        "headers": list(csv_template_headers()),
    })


@require_POST
@login_required
def create_portal_account_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Create an Employee-role User linked to this employee. Admin then sends a password reset."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise PermissionDenied("Tenant subdomain required.")
    if request.user.role not in (Role.COMPANY_ADMIN, Role.PAYROLL_MANAGER):
        raise PermissionDenied("Only admins or payroll managers may create portal accounts.")

    employee = get_object_or_404(Employee, pk=pk)
    if employee.user_id is not None:
        messages.warning(request, "This employee already has a portal account.")
        return redirect("employees:detail", pk=pk)
    if not employee.work_email:
        messages.error(
            request,
            "Set a work email on the employee before creating a portal account.",
        )
        return redirect("employees:detail", pk=pk)

    try:
        new_user = User.objects.create_user(  # type: ignore[misc]
            email=employee.work_email,
            password=None,
            role=Role.EMPLOYEE,
            company=tenant,
        )
    except IntegrityError:
        messages.error(
            request,
            f"A user with email {employee.work_email} already exists.",
        )
        return redirect("employees:detail", pk=pk)

    employee.user = new_user
    employee.save(update_fields=["user", "updated_at"])
    messages.success(
        request,
        f"Portal account created for {employee.work_email}. "
        "Send them the password-reset link so they can set their password.",
    )
    return redirect("employees:detail", pk=pk)


@login_required
def csv_template_view(request: HttpRequest) -> HttpResponse:
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    if request.user.role == Role.EMPLOYEE:
        raise PermissionDenied("Employee self-service cannot access this resource.")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(csv_template_headers())
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="employees-template.csv"'
    return response
