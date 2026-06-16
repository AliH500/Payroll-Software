from django.contrib import admin

from apps.employees.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin[Employee]):
    list_display = (
        "employee_code", "last_name", "first_name", "company",
        "is_active", "hire_date",
    )
    list_filter = ("company", "is_active")
    search_fields = ("employee_code", "first_name", "last_name", "work_email")
    # Inspect a single record via Django admin even though querysets are
    # tenant-scoped at the manager layer; super-admin uses `all_tenants` here.
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        # tenant-bypass-allowed: Django admin is super-admin-only and crosses tenants
        return Employee.all_tenants.all()  # type: ignore[misc]
