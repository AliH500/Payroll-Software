import pytest

from apps.tenants.context import (
    get_current_tenant,
    require_current_tenant,
    tenant_context,
)
from apps.tenants.models import Company


@pytest.mark.django_db
def test_get_current_tenant_returns_none_outside_any_context():
    assert get_current_tenant() is None


@pytest.mark.django_db
def test_require_current_tenant_raises_without_a_binding():
    with pytest.raises(RuntimeError):
        require_current_tenant()


@pytest.mark.django_db
def test_tenant_context_binds_then_restores():
    acme = Company.objects.create(slug="acme", name="Acme", country="PK", currency="PKR")
    assert get_current_tenant() is None
    with tenant_context(acme):
        assert get_current_tenant() == acme
    assert get_current_tenant() is None


@pytest.mark.django_db
def test_tenant_context_nests_and_restores_outer():
    a = Company.objects.create(slug="a", name="A", country="PK", currency="PKR")
    b = Company.objects.create(slug="b", name="B", country="ET", currency="ETB")
    with tenant_context(a):
        assert get_current_tenant() == a
        with tenant_context(b):
            assert get_current_tenant() == b
        assert get_current_tenant() == a
    assert get_current_tenant() is None
