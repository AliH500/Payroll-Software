from __future__ import annotations

from django import forms

from apps.compensation.models import Bonus, Deduction, ExpenseReimbursement
from apps.employees.models import Employee
from apps.payroll.models import PayPeriod


class _BaseCompensationForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        fields = ["employee", "period", "description", "amount"]

    def __init__(self, *args, tenant=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["employee"].queryset = Employee.all_tenants.filter(  # type: ignore[union-attr,misc]
                company=tenant, is_active=True,
            )
            self.fields["period"].queryset = PayPeriod.all_tenants.filter(  # type: ignore[union-attr,misc]
                company=tenant, status="open",
            )
            self.fields["amount"].label = f"Amount ({tenant.currency})"


class BonusForm(_BaseCompensationForm):
    class Meta(_BaseCompensationForm.Meta):
        model = Bonus


class DeductionForm(_BaseCompensationForm):
    class Meta(_BaseCompensationForm.Meta):
        model = Deduction


class ReimbursementForm(_BaseCompensationForm):
    class Meta(_BaseCompensationForm.Meta):
        model = ExpenseReimbursement
