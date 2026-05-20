from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

from django import forms

from apps.employees.models import Employee, PayBasis
from apps.payroll.models import PayPeriod


class PayPeriodForm(forms.ModelForm[PayPeriod]):
    class Meta:
        model = PayPeriod
        fields = ["year", "month"]
        widgets = {
            "year": forms.NumberInput(attrs={"min": 2020, "max": 2099, "class": "form-control"}),
            "month": forms.Select(
                choices=[(i, date_cls(2026, i, 1).strftime("%B")) for i in range(1, 13)],
                attrs={"class": "form-control"},
            ),
        }


class RunPayrollForm(forms.Form):
    """Dynamic form: one hours / units field per hourly / unit employee for the period."""

    def __init__(self, *args, period: PayPeriod, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.period = period
        self.dynamic_employees: list[Employee] = list(
            # tenant-bypass-allowed: form is filtered by period.company on the same line
            Employee.all_tenants.filter(  # type: ignore[misc]
                company=period.company, is_active=True,
            ).exclude(pay_basis=PayBasis.FIXED)
        )
        for emp in self.dynamic_employees:
            if emp.pay_basis == PayBasis.HOURLY:
                self.fields[f"hours_{emp.pk}"] = forms.DecimalField(
                    label=f"{emp.full_name} — hours worked",
                    max_digits=12, decimal_places=2, min_value=Decimal("0"),
                    widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
                    required=True,
                )
            elif emp.pay_basis == PayBasis.UNIT:
                self.fields[f"units_{emp.pk}"] = forms.DecimalField(
                    label=f"{emp.full_name} — units processed",
                    max_digits=12, decimal_places=2, min_value=Decimal("0"),
                    widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
                    required=True,
                )

    def hours_by_employee(self) -> dict[int, Decimal]:
        out: dict[int, Decimal] = {}
        for emp in self.dynamic_employees:
            if emp.pay_basis == PayBasis.HOURLY:
                v = self.cleaned_data.get(f"hours_{emp.pk}")
                if v is not None:
                    out[emp.pk] = Decimal(v)
        return out

    def units_by_employee(self) -> dict[int, Decimal]:
        out: dict[int, Decimal] = {}
        for emp in self.dynamic_employees:
            if emp.pay_basis == PayBasis.UNIT:
                v = self.cleaned_data.get(f"units_{emp.pk}")
                if v is not None:
                    try:
                        out[emp.pk] = Decimal(v)
                    except InvalidOperation:
                        continue
        return out
