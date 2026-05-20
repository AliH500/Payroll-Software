"""Request-scoped current-tenant binding.

A `ContextVar` is used so the binding is safe across threads, async tasks, and
nested calls. The TenantResolutionMiddleware sets and resets it on every request;
non-request code (management commands, background jobs) must use the
`tenant_context` context manager to bind explicitly.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.tenants.models import Company

current_tenant: ContextVar[Company | None] = ContextVar("current_tenant", default=None)


def get_current_tenant() -> Company | None:
    return current_tenant.get()


def require_current_tenant() -> Company:
    tenant = current_tenant.get()
    if tenant is None:
        raise RuntimeError(
            "No tenant in the current request context. "
            "Tenant-scoped queries require a Company; use Model.all_tenants for "
            "intentional cross-tenant access (super-admin, migrations)."
        )
    return tenant


@contextmanager
def tenant_context(tenant: Company | None) -> Iterator[None]:
    """Bind the given tenant for the duration of the block, then restore the prior value."""
    token = current_tenant.set(tenant)
    try:
        yield
    finally:
        current_tenant.reset(token)
