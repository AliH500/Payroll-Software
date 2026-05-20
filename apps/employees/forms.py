from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.employees.models import Employee, PayBasis


class EmployeeForm(forms.ModelForm[Employee]):
    """Edit form for an Employee. Enforces 'exactly one pay rate field populated per pay_basis'."""

    class Meta:
        model = Employee
        fields = [
            "first_name",
            "last_name",
            "work_email",
            "phone",
            "national_id",
            "passport_number",
            "passport_expiry",
            "visa_number",
            "visa_expiry",
            "bank_account_number",
            "pay_basis",
            "base_salary",
            "hourly_rate",
            "unit_rate",
            "hire_date",
            "is_active",
        ]
        widgets = {
            "passport_expiry": forms.DateInput(attrs={"type": "date"}),
            "visa_expiry": forms.DateInput(attrs={"type": "date"}),
            "hire_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        if tenant is not None:
            currency = tenant.currency
            self.fields["base_salary"].label = f"Base salary ({currency})"
            self.fields["hourly_rate"].label = f"Hourly rate ({currency})"
            self.fields["unit_rate"].label = f"Unit rate ({currency})"

    def clean(self) -> dict[str, object] | None:
        cleaned = super().clean()
        if cleaned is None:
            return None
        basis_value = cleaned.get("pay_basis")
        basis_to_field = {
            PayBasis.FIXED.value: "base_salary",
            PayBasis.HOURLY.value: "hourly_rate",
            PayBasis.UNIT.value: "unit_rate",
        }
        rate_field = basis_to_field.get(str(basis_value)) if basis_value else None
        if rate_field and not cleaned.get(rate_field):
            self.add_error(rate_field, _("Required for the selected pay basis."))
        for f in ("base_salary", "hourly_rate", "unit_rate"):
            if f != rate_field:
                cleaned[f] = None
        return cleaned

    def clean_pay_basis(self) -> str:
        basis = self.cleaned_data.get("pay_basis")
        if basis not in PayBasis.values:
            raise ValidationError(_("Pick a valid pay basis."))
        return str(basis)
