from django.contrib import admin

from apps.attendance.models import AttendanceRecord, AttendanceSheet


@admin.register(AttendanceSheet)
class AttendanceSheetAdmin(admin.ModelAdmin[AttendanceSheet]):
    list_display = ("period", "company", "total_working_days", "updated_at")
    list_filter = ("company",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        # tenant-bypass-allowed: Django admin is super-admin-only and crosses tenants
        return AttendanceSheet.all_tenants.all()


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin[AttendanceRecord]):
    list_display = (
        "employee", "sheet", "days_present", "days_late",
        "days_absent", "days_absent_without_leave", "days_leave",
    )
    list_filter = ("company",)
    search_fields = ("employee__employee_code", "employee__first_name", "employee__last_name")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        # tenant-bypass-allowed: Django admin is super-admin-only and crosses tenants
        return AttendanceRecord.all_tenants.all()
