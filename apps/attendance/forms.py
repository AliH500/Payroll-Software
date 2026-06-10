from __future__ import annotations

from django import forms

from apps.attendance.models import AttendanceSheet


class AttendanceSheetForm(forms.ModelForm[AttendanceSheet]):
    class Meta:
        model = AttendanceSheet
        fields = ["total_working_days"]
        widgets = {
            "total_working_days": forms.NumberInput(
                attrs={"min": 0, "max": 31, "class": "form-control"},
            ),
        }
        labels = {"total_working_days": "Total working days this month"}
