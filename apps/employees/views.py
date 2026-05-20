from __future__ import annotations

import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.employees.csv_import import csv_template_headers, import_employees
from apps.employees.forms import EmployeeForm
from apps.employees.models import Employee


class _TenantRequiredMixin(LoginRequiredMixin):
    """Reject anonymous + super-admin-on-bare-domain requests."""

    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("This page is only available on a tenant subdomain.")
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


@login_required
def csv_template_view(request: HttpRequest) -> HttpResponse:
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(csv_template_headers())
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="employees-template.csv"'
    return response
