from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", _("Super Admin")
    COMPANY_ADMIN = "company_admin", _("Company Admin")
    PAYROLL_MANAGER = "payroll_manager", _("Payroll Manager")
    VIEWER = "viewer", _("Viewer")
    EMPLOYEE = "employee", _("Employee Self-Service")


class UserManager(BaseUserManager["User"]):
    """Manager for the email-as-username custom User."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> User:
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.SUPER_ADMIN)
        extra_fields.setdefault("company", None)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Email-keyed user bound to a single Company, except for super-admins.

    Super-admins (role=super_admin) operate the platform across tenants and
    must have `company` unset. Every other role is bound to exactly one Company.
    """

    username = None  # type: ignore[assignment]
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)

    company = models.ForeignKey(
        "tenants.Company",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
        help_text=_("Tenant the user is scoped to. Null only for super-admins."),
    )
    role = models.CharField(
        _("role"),
        max_length=32,
        choices=Role.choices,
    )

    USERNAME_FIELD = "email"
    # django-stubs inherits AbstractUser's instance-var declaration; we re-annotate intentionally.
    REQUIRED_FIELDS: list[str] = []  # type: ignore[misc]

    objects = UserManager()  # type: ignore[assignment,misc]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["email"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(role=Role.SUPER_ADMIN, company__isnull=True)
                    | (~models.Q(role=Role.SUPER_ADMIN) & models.Q(company__isnull=False))
                ),
                name="super_admin_xor_company",
            ),
        ]

    def __str__(self) -> str:
        return self.email
