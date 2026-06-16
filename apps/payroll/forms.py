from __future__ import annotations

from datetime import date as date_cls

from django import forms

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
    """Confirm-only form. Every employee is salaried, so payroll needs no per-employee
    runtime input — salary and allowances live on the Employee record."""
