from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.tenants.context import current_tenant
from apps.tenants.models import Company


class TenantResolutionMiddleware:
    """Resolve the tenant from the request host's subdomain and bind it for the request.

    Resolution rules:
    - Host equals `settings.TENANT_BASE_DOMAIN` -> no tenant (super-admin / public surfaces).
    - Host is `<slug>.<TENANT_BASE_DOMAIN>` -> look up Company by `slug`; bind if active.
    - Multi-label subdomains, unknown slugs, and inactive companies -> no tenant.

    The tenant is bound to both `request.tenant` (for view convenience) and the
    `current_tenant` ContextVar (for manager/ORM-level scoping).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tenant = self._resolve_tenant(request)
        request.tenant = tenant  # type: ignore[attr-defined]
        token = current_tenant.set(tenant)
        try:
            return self.get_response(request)
        finally:
            current_tenant.reset(token)

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
