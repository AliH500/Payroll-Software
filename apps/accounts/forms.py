from __future__ import annotations

from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Role, User


class TenantScopedAuthenticationForm(AuthenticationForm):
    """Login form that also enforces the host-to-account binding.

    - Super-admins can only sign in on the bare base domain.
    - Every other role must sign in on a subdomain that matches their Company.
    """

    def confirm_login_allowed(self, user: User) -> None:
        super().confirm_login_allowed(user)
        tenant = getattr(self.request, "tenant", None)
        if user.role == Role.SUPER_ADMIN:
            if tenant is not None:
                raise ValidationError(
                    _(
                        "Super-admins must sign in on the platform admin domain, "
                        "not a tenant subdomain."
                    ),
                    code="wrong_domain",
                )
        elif user.company_id != getattr(tenant, "id", None):
            raise ValidationError(
                _("This account doesn't have access to this company."),
                code="wrong_tenant",
            )
