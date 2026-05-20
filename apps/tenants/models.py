from django.core.validators import RegexValidator
from django.db import models


class Country(models.TextChoices):
    PAKISTAN = "PK", "Pakistan"
    ETHIOPIA = "ET", "Ethiopia"


class Currency(models.TextChoices):
    PKR = "PKR", "Pakistani Rupee"
    ETB = "ETB", "Ethiopian Birr"


# RFC 1035 label: 1-63 chars, lowercase alphanumerics and hyphens, no leading/trailing hyphen.
SUBDOMAIN_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    message=(
        "Slug must be 1-63 chars, lowercase letters/digits/hyphens, "
        "no leading or trailing hyphen."
    ),
)


class Company(models.Model):
    """Tenant root. Every multi-tenant row links back to exactly one Company."""

    slug = models.SlugField(
        max_length=63,
        unique=True,
        validators=[SUBDOMAIN_VALIDATOR],
        help_text="DNS-safe subdomain identifier (e.g. 'acme' for acme.payroll.example.com).",
    )
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=2, choices=Country.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"
