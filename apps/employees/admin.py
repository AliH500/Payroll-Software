from django.contrib import admin

from apps.employees.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin[Employee]):
    list_display = ("last_name", "first_name", "company", "pay_basis", "is_active", "hire_date")
    list_filter = ("company", "pay_basis", "is_active")
    search_fields = ("first_name", "last_name", "work_email")
    # Inspect a single record via Django admin even though querysets are
    # tenant-scoped at the manager layer; super-admin uses `all_tenants` here.
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        return Employee.all_tenants.all()  # type: ignore[misc]
