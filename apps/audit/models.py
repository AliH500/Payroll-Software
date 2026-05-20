from __future__ import annotations

from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"


class AuditLogEntry(models.Model):
    """Append-only record of mutations to tenant-scoped models.

    Per-tenant isolation is enforced by `company`. The CI guard checks that all
    queries here are filtered by company (super-admin reports are the only
    legitimate cross-tenant reads).

    `metadata` MUST NOT contain sensitive values (salary, PII identifiers, etc.).
    Record field NAMES that changed, never the new/old values themselves.
    """

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.PROTECT,
        related_name="audit_entries",
    )
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
        help_text="User who performed the action; null for system-initiated changes.",
    )
    action = models.CharField(max_length=16, choices=AuditAction.choices)
    target_model = models.CharField(
        max_length=200,
        help_text="App-qualified model label, e.g. 'employees.Employee'.",
    )
    target_id = models.CharField(
        max_length=64,
        help_text="Primary key of the target row, stringified.",
    )
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "audit log entry"
        verbose_name_plural = "audit log entries"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["company", "-occurred_at"]),
            models.Index(fields=["target_model", "target_id"]),
        ]

    def __str__(self) -> str:
        ts = self.occurred_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.action} {self.target_model}#{self.target_id} @ {ts}"
