from django.contrib import admin

from apps.audit.models import AuditLogEntry


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin[AuditLogEntry]):
    list_display = ("occurred_at", "company", "actor", "action", "target_model", "target_id")
    list_filter = ("action", "target_model", "company")
    search_fields = ("target_model", "target_id", "actor__email")
    readonly_fields = (
        "company",
        "actor",
        "action",
        "target_model",
        "target_id",
        "occurred_at",
        "metadata",
    )
    date_hierarchy = "occurred_at"

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
