from django.db import models

from apps.tenants.managers import TenantManager


class TenantAwareModel(models.Model):
    """Abstract base for any model whose rows belong to exactly one Company.

    - `company` FK uses PROTECT so a Company cannot be deleted while data exists.
    - `objects` is the auto-scoping TenantManager (fails loud without context).
    - `all_tenants` is the unscoped escape hatch; usage on PII-sensitive models is
      flagged by the CI guard.
    """

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        abstract = True
