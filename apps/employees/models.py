from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models_base import TenantAwareModel
from domain.money import Money
from services.encryption import EncryptedDecimalField, EncryptedTextField


class Employee(TenantAwareModel):
    """An employee of a Company. PII identifiers and salary values are encrypted at rest."""

    # Company-assigned identifier, unique within the company. Used to map CSV
    # imports (employees and attendance) to the right person. Not PII — plain text.
    employee_code = models.CharField(max_length=64)
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

    # Compensation — encrypted. Every employee is salaried; allowances and the
    # performance bonus are fixed monthly amounts that default to zero.
    salary = EncryptedDecimalField()
    conveyance_allowance = EncryptedDecimalField(blank=True, default=Decimal("0"))
    attendance_allowance = EncryptedDecimalField(blank=True, default=Decimal("0"))
    performance_bonus = EncryptedDecimalField(blank=True, default=Decimal("0"))

    hire_date = models.DateField()
    is_active = models.BooleanField(default=True)

    user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
        help_text=_("Optional self-service portal account for this employee."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("employee")
        verbose_name_plural = _("employees")
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_code"],
                name="unique_company_employee_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or f"Employee #{self.pk}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def salary_money(self) -> Money:
        """Monthly salary as a Money (redacts in repr/str)."""
        return Money(self.salary, self.company.currency)

    def conveyance_allowance_money(self) -> Money:
        return Money(self.conveyance_allowance, self.company.currency)

    def attendance_allowance_money(self) -> Money:
        return Money(self.attendance_allowance, self.company.currency)

    def performance_bonus_money(self) -> Money:
        return Money(self.performance_bonus, self.company.currency)
