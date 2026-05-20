from django.contrib import admin

from apps.tenants.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin[Company]):
    list_display = ("name", "slug", "country", "currency", "is_active", "created_at")
    list_filter = ("country", "currency", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
