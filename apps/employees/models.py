from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models_base import TenantAwareModel
from domain.money import Money
from services.encryption import EncryptedDecimalField, EncryptedTextField


class PayBasis(models.TextChoices):
    FIXED = "fixed", _("Fixed monthly salary")
    HOURLY = "hourly", _("Hourly")
    UNIT = "unit", _("Unit-based")


class Employee(TenantAwareModel):
    """An employee of a Company. PII identifiers and salary values are encrypted at rest."""

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    work_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)

    # PII identifiers — encrypted-at-rest. Not queryable by SQL.
    national_id = EncryptedTextField(blank=True, null=True)
    passport_number = EncryptedTextField(blank=True, null=True)
    passport_expiry = models.DateField(null=True, blank=True)
    visa_number = EncryptedTextField(blank=True, null=True)
    visa_expiry = models.DateField(null=True, blank=True)
    bank_account_number = EncryptedTextField(blank=True, null=True)

    # Compensation — encrypted. Exactly one of these should be populated per pay_basis.
    pay_basis = models.CharField(max_length=16, choices=PayBasis.choices)
    base_salary = EncryptedDecimalField(blank=True, null=True)
    hourly_rate = EncryptedDecimalField(blank=True, null=True)
    unit_rate = EncryptedDecimalField(blank=True, null=True)

    hire_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("employee")
        verbose_name_plural = _("employees")
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or f"Employee #{self.pk}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def pay_rate(self) -> Decimal | None:
        """The active pay rate for the current pay_basis (Decimal, not Money)."""
        rate: Any
        if self.pay_basis == PayBasis.FIXED:
            rate = self.base_salary
        elif self.pay_basis == PayBasis.HOURLY:
            rate = self.hourly_rate
        elif self.pay_basis == PayBasis.UNIT:
            rate = self.unit_rate
        else:
            return None
        if rate is None:
            return None
        return rate if isinstance(rate, Decimal) else Decimal(str(rate))

    def pay_rate_money(self) -> Money | None:
        """The active pay rate as a Money (redacts in repr/str)."""
        rate = self.pay_rate
        if rate is None:
            return None
        return Money(rate, self.company.currency)
