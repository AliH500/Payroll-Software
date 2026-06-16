from __future__ import annotations

from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models_base import TenantAwareModel


class AttendanceSheet(TenantAwareModel):
    """One month's attendance for a company, tied to a pay period.

    Holds the company-wide total working days for the month; per-employee day
    counts live on AttendanceRecord. Day counts are not salary or PII, so the
    fields are plain integers (no encryption).
    """

    period = models.OneToOneField(
        "payroll.PayPeriod",
        on_delete=models.CASCADE,
        related_name="attendance_sheet",
    )
    total_working_days = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(31)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("attendance sheet")
        verbose_name_plural = _("attendance sheets")
        ordering = ["-period__year", "-period__month"]

    def __str__(self) -> str:
        return f"Attendance — period {self.period_id}"


class AttendanceRecord(TenantAwareModel):
    """One employee's attendance for one month."""

    sheet = models.ForeignKey(
        AttendanceSheet, on_delete=models.CASCADE, related_name="records",
    )
    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.PROTECT, related_name="attendance_records",
    )

    days_present = models.PositiveSmallIntegerField(default=0)
    days_late = models.PositiveSmallIntegerField(default=0)
    # Total absent is the sum of plain absences and leaves; kept explicit so the
    # CSV can be validated against days_absent + days_leave.
    days_total_absent = models.PositiveSmallIntegerField(default=0)
    days_absent = models.PositiveSmallIntegerField(default=0)
    days_leave = models.PositiveSmallIntegerField(default=0)
    # Weekends + national holidays. Record-only; does not affect pay yet.
    off_days = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("attendance record")
        verbose_name_plural = _("attendance records")
        ordering = ["employee__last_name", "employee__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "employee"],
                name="unique_sheet_employee_attendance",
            ),
        ]

    def __str__(self) -> str:
        return f"Attendance {self.employee_id} — sheet {self.sheet_id}"
