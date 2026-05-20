from django.contrib import admin

from apps.compensation.models import Bonus, Deduction, ExpenseReimbursement


class _BaseAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("employee", "period", "description", "created_at")
    list_filter = ("period",)
    search_fields = ("employee__first_name", "employee__last_name", "description")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        return self.model.all_tenants.all()  # type: ignore[misc]


@admin.register(Bonus)
class BonusAdmin(_BaseAdmin):
    pass


@admin.register(Deduction)
class DeductionAdmin(_BaseAdmin):
    pass


@admin.register(ExpenseReimbursement)
class ExpenseReimbursementAdmin(_BaseAdmin):
    pass
