from __future__ import annotations

import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from apps.accounts.models import Role
from apps.attendance.csv_import import (
    COUNT_COLUMNS,
    csv_template_headers,
    import_attendance,
)
from apps.attendance.forms import AttendanceSheetForm
from apps.attendance.models import AttendanceRecord, AttendanceSheet
from apps.employees.models import Employee
from apps.payroll.models import PayPeriod

# Maps a grid input prefix to the matching model field.
_GRID_FIELDS = {
    "present": "days_present",
    "late": "days_late",
    "absent": "days_absent",
    "awol": "days_absent_without_leave",
    "leave": "days_leave",
}


class _TenantRequiredMixin(LoginRequiredMixin):
    """Reject anonymous, non-tenant, and employee-role requests."""

    def dispatch(self, request: HttpRequest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if getattr(request, "tenant", None) is None:
            raise PermissionDenied("This page is only available on a tenant subdomain.")
        if request.user.role == Role.EMPLOYEE:
            raise PermissionDenied("This area is for company admins, not employee self-service.")
        return super().dispatch(request, *args, **kwargs)


def _require_admin(request: HttpRequest) -> None:
    if not request.user.is_authenticated:
        raise PermissionDenied("Login required.")
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    if request.user.role == Role.EMPLOYEE:
        raise PermissionDenied("Employee self-service cannot manage attendance.")


class AttendancePeriodListView(_TenantRequiredMixin, ListView[PayPeriod]):
    """Pick the month whose attendance you want to record."""

    model = PayPeriod
    template_name = "attendance/period_list.html"
    context_object_name = "periods"


def _get_or_create_sheet(period: PayPeriod, tenant: object) -> AttendanceSheet:
    sheet, _ = AttendanceSheet.objects.get_or_create(
        period=period, defaults={"company": tenant},
    )
    return sheet


def _parse_grid(post: dict[str, str], employees: list[Employee]) -> tuple[
    dict[int, dict[str, int]], dict[int, str],
]:
    """Return (values_by_employee, errors_by_employee) from POSTed grid inputs."""
    values: dict[int, dict[str, int]] = {}
    errors: dict[int, str] = {}
    for emp in employees:
        row: dict[str, int] = {}
        for prefix, field in _GRID_FIELDS.items():
            raw = (post.get(f"{prefix}_{emp.pk}") or "").strip()
            if not raw:
                row[field] = 0
                continue
            try:
                parsed = int(raw)
            except ValueError:
                errors[emp.pk] = "Enter whole numbers only."
                break
            if parsed < 0:
                errors[emp.pk] = "Day counts cannot be negative."
                break
            row[field] = parsed
        else:
            values[emp.pk] = row
    return values, errors


@login_required
def attendance_sheet_view(request: HttpRequest, period_pk: int) -> HttpResponse:
    _require_admin(request)
    tenant = request.tenant  # type: ignore[attr-defined]
    period = get_object_or_404(PayPeriod, pk=period_pk)
    sheet = _get_or_create_sheet(period, tenant)
    employees = list(Employee.objects.filter(is_active=True).order_by("last_name", "first_name"))

    grid_errors: dict[int, str] = {}
    if request.method == "POST":
        form = AttendanceSheetForm(request.POST, instance=sheet)
        values, grid_errors = _parse_grid(request.POST, employees)
        if period.is_closed:
            messages.error(request, "This period is closed; attendance is locked.")
        elif form.is_valid() and not grid_errors:
            form.save()
            for emp in employees:
                AttendanceRecord.objects.update_or_create(
                    sheet=sheet, employee=emp,
                    defaults={"company": tenant, **values[emp.pk]},
                )
            messages.success(request, f"Saved attendance for {period.label}.")
            return redirect("attendance:sheet", period_pk=period.pk)
    else:
        form = AttendanceSheetForm(instance=sheet)

    records = {r.employee_id: r for r in AttendanceRecord.objects.filter(sheet=sheet)}
    rows = [
        {"employee": emp, "record": records.get(emp.pk), "error": grid_errors.get(emp.pk)}
        for emp in employees
    ]
    return render(request, "attendance/sheet.html", {
        "period": period,
        "sheet": sheet,
        "form": form,
        "rows": rows,
        "count_columns": COUNT_COLUMNS,
    })


@login_required
def attendance_import_view(request: HttpRequest, period_pk: int) -> HttpResponse:
    _require_admin(request)
    tenant = request.tenant  # type: ignore[attr-defined]
    period = get_object_or_404(PayPeriod, pk=period_pk)
    if period.is_closed:
        messages.error(request, "This period is closed; attendance is locked.")
        return redirect("attendance:sheet", period_pk=period.pk)
    sheet = _get_or_create_sheet(period, tenant)

    if request.method == "POST" and request.FILES.get("file"):
        outcomes = import_attendance(sheet, request.FILES["file"].read())
        successes = sum(1 for o in outcomes if o.ok)
        failures = len(outcomes) - successes
        if successes:
            messages.success(request, f"Recorded attendance for {successes} employee(s).")
        if failures:
            messages.warning(request, f"{failures} row(s) had errors; see report below.")
        return render(request, "attendance/import.html", {
            "period": period,
            "outcomes": outcomes,
            "headers": list(csv_template_headers()),
        })

    return render(request, "attendance/import.html", {
        "period": period,
        "outcomes": None,
        "headers": list(csv_template_headers()),
    })


@login_required
def attendance_template_view(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(csv_template_headers())
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="attendance-template.csv"'
    return response
