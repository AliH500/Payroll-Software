from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse

from apps.tenants.context import current_tenant
from apps.tenants.models import Company


class TenantResolutionMiddleware:
    """Resolve the tenant from the request host's subdomain and bind it for the request.

    Resolution rules:
    - Host equals `settings.TENANT_BASE_DOMAIN` -> no tenant (super-admin / public surfaces).
    - Host is `<slug>.<TENANT_BASE_DOMAIN>` -> look up Company by `slug`; bind if active.
    - Multi-label subdomains, unknown slugs, and inactive companies -> no tenant.

    The tenant is bound to:
    - `request.tenant` (for view convenience),
    - the `current_tenant` ContextVar (for manager/ORM-level scoping),
    - Postgres session GUCs `app.current_tenant_id` and `app.is_super_admin`
      (for the RLS policies on PII tables — layer three of the defense).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tenant = self._resolve_tenant(request)
        request.tenant = tenant  # type: ignore[attr-defined]
        token = current_tenant.set(tenant)
        self._apply_rls_session_vars(request, tenant)
        try:
            return self.get_response(request)
        finally:
            current_tenant.reset(token)

    @staticmethod
    def _apply_rls_session_vars(request: HttpRequest, tenant: Company | None) -> None:
        """Set Postgres session GUCs for RLS policies.

        Always set both keys (even when empty) so RLS sees a stable, non-missing value.
        Super-admin status is granted only when the user is authenticated as super_admin
        AND on the bare domain (no tenant resolved).
        """
        tenant_id = str(tenant.pk) if tenant is not None else ""
        is_super = "false"
        user = getattr(request, "user", None)
        if (
            tenant is None
            and user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "role", None) == "super_admin"
        ):
            is_super = "true"
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, false), "
                "set_config('app.is_super_admin', %s, false)",
                [tenant_id, is_super],
            )

    @staticmethod
    def _resolve_tenant(request: HttpRequest) -> Company | None:
        host = request.get_host().split(":", 1)[0].lower()
        base = settings.TENANT_BASE_DOMAIN.split(":", 1)[0].lower()

        if host == base:
            return None

        suffix = "." + base
        if not host.endswith(suffix):
            return None

        slug = host[: -len(suffix)]
        if not slug or "." in slug:
            return None

        return Company.objects.filter(slug=slug, is_active=True).first()
