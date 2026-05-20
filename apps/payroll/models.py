from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models_base import TenantAwareModel
from domain.money import Money
from services.encryption import EncryptedDecimalField


class PeriodStatus(models.TextChoices):
    OPEN = "open", _("Open")
    CLOSED = "closed", _("Closed")


class PayPeriod(TenantAwareModel):
    """A monthly pay period for a Company. Closed periods are immutable."""

    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=16, choices=PeriodStatus.choices, default=PeriodStatus.OPEN,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "month"],
                name="unique_company_period",
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12),
                name="period_month_1_to_12",
            ),
        ]
        ordering = ["-year", "-month"]

    @property
    def label(self) -> str:
        return f"{date(self.year, self.month, 1):%B %Y}"

    @property
    def is_closed(self) -> bool:
        return self.status == PeriodStatus.CLOSED

    def __str__(self) -> str:
        return self.label

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            existing = PayPeriod.all_tenants.filter(pk=self.pk).first()  # type: ignore[misc]
            if existing is not None and existing.status == PeriodStatus.CLOSED:
                # Allow closing-time fields to update once via close_period() path
                # but not arbitrary edits after closure.
                changed = {
                    f.name for f in self._meta.fields
                    if getattr(self, f.name) != getattr(existing, f.name)
                }
                if changed - {"status", "closed_at", "closed_by", "updated_at"}:
                    raise ValidationError("Closed pay periods are immutable.")
        super().save(*args, **kwargs)


class Payslip(TenantAwareModel):
    """A computed payslip for one employee in one pay period."""

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.PROTECT, related_name="payslips",
    )
    period = models.ForeignKey(
        PayPeriod, on_delete=models.PROTECT, related_name="payslips",
    )

    # Inputs captured at run time, encrypted.
    hours_worked = EncryptedDecimalField(blank=True, null=True)
    units_processed = EncryptedDecimalField(blank=True, null=True)

    # Computed totals, encrypted.
    base_pay = EncryptedDecimalField()
    bonuses_total = EncryptedDecimalField()
    deductions_total = EncryptedDecimalField()
    reimbursements_total = EncryptedDecimalField()
    net_pay = EncryptedDecimalField()

    currency = models.CharField(max_length=3)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["employee", "period"], name="unique_employee_period"),
        ]
        ordering = ["-period__year", "-period__month", "employee__last_name"]

    def __str__(self) -> str:
        return f"Payslip {self.employee_id} {self.period_id}"

    def base_pay_money(self) -> Money:
        return Money(self.base_pay, self.currency)

    def bonuses_money(self) -> Money:
        return Money(self.bonuses_total, self.currency)

    def deductions_money(self) -> Money:
        return Money(self.deductions_total, self.currency)

    def reimbursements_money(self) -> Money:
        return Money(self.reimbursements_total, self.currency)

    def net_pay_money(self) -> Money:
        return Money(self.net_pay, self.currency)


class PayslipLine(models.Model):
    """Itemised line on a Payslip. Stored without TenantAware because access goes via the parent."""

    class LineType(models.TextChoices):
        BASE = "base", _("Base pay")
        BONUS = "bonus", _("Bonus")
        DEDUCTION = "deduction", _("Deduction")
        REIMBURSEMENT = "reimbursement", _("Reimbursement")

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=16, choices=LineType.choices)
    description = models.CharField(max_length=200)
    amount = EncryptedDecimalField()

    class Meta:
        ordering = ["line_type", "id"]

    def amount_money(self) -> Money:
        return Money(self.amount, self.payslip.currency)

    def __str__(self) -> str:
        return f"{self.get_line_type_display()}: {self.description}"
