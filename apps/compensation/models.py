from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models_base import TenantAwareModel
from domain.money import Money
from services.encryption import EncryptedDecimalField


class _CompensationLine(TenantAwareModel):
    """Abstract base for one-off per-period compensation adjustments."""

    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="+")
    period = models.ForeignKey("payroll.PayPeriod", on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=200)
    amount = EncryptedDecimalField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def amount_money(self) -> Money:
        return Money(self.amount, self.company.currency)


class Bonus(_CompensationLine):
    class Meta(_CompensationLine.Meta):
        verbose_name = _("bonus")
        verbose_name_plural = _("bonuses")


class Deduction(_CompensationLine):
    class Meta(_CompensationLine.Meta):
        verbose_name = _("deduction")
        verbose_name_plural = _("deductions")


class ExpenseReimbursement(_CompensationLine):
    class Meta(_CompensationLine.Meta):
        verbose_name = _("expense reimbursement")
        verbose_name_plural = _("expense reimbursements")
