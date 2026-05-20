from django.contrib import admin

from apps.payroll.models import PayPeriod, Payslip, PayslipLine


@admin.register(PayPeriod)
class PayPeriodAdmin(admin.ModelAdmin[PayPeriod]):
    list_display = ("__str__", "company", "status", "closed_at")
    list_filter = ("company", "status", "year")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        return PayPeriod.all_tenants.all()  # type: ignore[misc]


class PayslipLineInline(admin.TabularInline[PayslipLine, Payslip]):
    model = PayslipLine
    extra = 0
    readonly_fields = ("line_type", "description", "amount")


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin[Payslip]):
    list_display = ("employee", "period", "currency", "generated_at")
    list_filter = ("period__year", "currency")
    inlines = [PayslipLineInline]

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        # tenant-bypass-allowed: Django admin is super-admin-only and crosses tenants
        return Payslip.all_tenants.all()  # type: ignore[misc]
