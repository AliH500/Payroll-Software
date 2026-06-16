from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.employees.models import Employee


class EmployeeForm(forms.ModelForm[Employee]):
    """Create/edit form for an Employee. Every employee is salaried."""

    class Meta:
        model = Employee
        fields = [
            "employee_code",
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
            "salary",
            "conveyance_allowance",
            "attendance_allowance",
            "performance_bonus",
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
        self.tenant = tenant
        self.fields["employee_code"].label = "Employee ID"
        self.fields["employee_code"].help_text = "Unique within your company."
        if tenant is not None:
            currency = tenant.currency
            self.fields["salary"].label = f"Monthly salary ({currency})"
            self.fields["conveyance_allowance"].label = f"Conveyance allowance ({currency})"
            self.fields["attendance_allowance"].label = f"Attendance allowance ({currency})"
            self.fields["performance_bonus"].label = f"Performance bonus ({currency})"

    def clean_employee_code(self) -> str:
        code = (self.cleaned_data.get("employee_code") or "").strip()
        if not code:
            raise ValidationError(_("Employee ID is required."))
        if self.tenant is not None:
            # tenant-bypass-allowed: uniqueness check is scoped to the form's tenant
            dupes = Employee.all_tenants.filter(company=self.tenant, employee_code=code)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise ValidationError(_("An employee with this ID already exists."))
        return code
