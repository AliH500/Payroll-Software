"""Write-side helpers for audit entries.

Resolves actor and tenant from the request ContextVars set by middleware.
Refuses to record when there is no tenant in context — every mutable action
in the system is supposed to happen inside a tenant scope.
"""

from __future__ import annotations

from typing import Any

from django.db import models

from apps.accounts.context import get_current_user
from apps.audit.models import AuditAction, AuditLogEntry
from apps.tenants.context import get_current_tenant


def record_audit(
    *,
    action: AuditAction | str,
    target: models.Model,
    metadata: dict[str, Any] | None = None,
) -> AuditLogEntry | None:
    """Persist an AuditLogEntry for the given target.

    Returns None silently when there is no tenant in context — this happens
    inside migrations and seed scripts, where audit doesn't apply.

    Callers must never pass sensitive values in `metadata`; record field NAMES
    that changed, not values.
    """
    tenant = get_current_tenant()
    if tenant is None:
        return None

    actor = get_current_user()
    return AuditLogEntry.objects.create(
        company=tenant,
        actor=actor,
        action=str(action),
        target_model=f"{target._meta.app_label}.{target._meta.object_name}",
        target_id=str(target.pk),
        metadata=metadata or {},
    )
