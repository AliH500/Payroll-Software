import pytest
from django.db.utils import IntegrityError

from apps.accounts.models import Role, User
from apps.tenants.models import Company


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(slug="acme", name="Acme", country="PK", currency="PKR")


@pytest.mark.django_db
def test_create_user_with_company(acme):
    user = User.objects.create_user(
        email="alice@acme.test",
        password="strong-password-123",
        company=acme,
        role=Role.COMPANY_ADMIN,
    )
    assert user.email == "alice@acme.test"
    assert user.check_password("strong-password-123")
    assert user.role == Role.COMPANY_ADMIN
    assert user.company == acme
    assert user.is_active
    assert not user.is_staff


@pytest.mark.django_db
def test_create_superuser_has_no_company():
    user = User.objects.create_superuser(
        email="ali@platform.test",
        password="another-strong-pass-123",
    )
    assert user.is_superuser
    assert user.is_staff
    assert user.role == Role.SUPER_ADMIN
    assert user.company is None


@pytest.mark.django_db
def test_super_admin_cannot_have_company(acme):
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email="bad@platform.test",
            password="x",
            role=Role.SUPER_ADMIN,
            company=acme,
        )


@pytest.mark.django_db
def test_non_super_admin_must_have_company():
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email="bad@platform.test",
            password="x",
            role=Role.COMPANY_ADMIN,
            company=None,
        )


@pytest.mark.django_db
def test_email_is_unique(acme):
    User.objects.create_user(
        email="dup@acme.test", password="x", company=acme, role=Role.VIEWER
    )
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email="dup@acme.test", password="x", company=acme, role=Role.VIEWER
        )


@pytest.mark.django_db
def test_email_is_normalized(acme):
    user = User.objects.create_user(
        email="Mixed.Case@Acme.Test",
        password="x",
        company=acme,
        role=Role.VIEWER,
    )
    assert user.email == "Mixed.Case@acme.test"


@pytest.mark.django_db
def test_create_user_requires_email(acme):
    with pytest.raises(ValueError):
        User.objects.create_user(
            email="", password="x", company=acme, role=Role.VIEWER
        )
