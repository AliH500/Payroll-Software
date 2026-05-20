from __future__ import annotations

from typing import TypeVar

from django.db import models

from apps.tenants.context import get_current_tenant

_M = TypeVar("_M", bound=models.Model)


class TenantManager(models.Manager[_M]):
    """Default manager for tenant-scoped models.

    Every queryset is auto-filtered to the tenant bound in the current request
    context. When no tenant is bound, the queryset is empty — a safe default
    that lets ModelForm class-definition introspection succeed without raising.

    Fail-loud guarantees live in the view layer (_TenantRequiredMixin returns
    403 if no tenant) and in the optional require_current_tenant() helper for
    explicit checks. The CI guard will scan for direct .objects access on
    PII-sensitive models that bypass the view-layer gate.

    For intentional cross-tenant access (super-admin tools, migrations, audit
    reports), use the `all_tenants` manager on the model instead.
    """

    def get_queryset(self) -> models.QuerySet[_M]:
        tenant = get_current_tenant()
        qs = super().get_queryset()
        if tenant is None:
            return qs.none()
        return qs.filter(company=tenant)
