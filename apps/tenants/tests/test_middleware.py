import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.tenants.context import get_current_tenant
from apps.tenants.middleware import TenantResolutionMiddleware
from apps.tenants.models import Company


def ok(_request: object) -> HttpResponse:
    return HttpResponse("ok")


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(
        slug="acme", name="Acme Imports", country="PK", currency="PKR"
    )


@pytest.mark.django_db
class TestTenantResolution:
    def test_root_domain_has_no_tenant(self, rf, settings):
        settings.TENANT_BASE_DOMAIN = "localhost"
        request = rf.get("/", HTTP_HOST="localhost:8000")
        TenantResolutionMiddleware(ok)(request)
        assert request.tenant is None

    def test_subdomain_resolves_tenant(self, rf, settings, acme):
        settings.TENANT_BASE_DOMAIN = "localhost"
        captured: dict = {}

        def capture(req):
            captured["tenant"] = req.tenant
            captured["contextvar"] = get_current_tenant()
            return HttpResponse("ok")

        TenantResolutionMiddleware(capture)(rf.get("/", HTTP_HOST="acme.localhost:8000"))

        assert captured["tenant"] == acme
        assert captured["contextvar"] == acme

    def test_unknown_subdomain_yields_no_tenant(self, rf, settings):
        settings.TENANT_BASE_DOMAIN = "localhost"
        request = rf.get("/", HTTP_HOST="ghost.localhost:8000")
        TenantResolutionMiddleware(ok)(request)
        assert request.tenant is None

    def test_inactive_company_is_not_bound(self, rf, settings, acme):
        settings.TENANT_BASE_DOMAIN = "localhost"
        acme.is_active = False
        acme.save()
        request = rf.get("/", HTTP_HOST="acme.localhost:8000")
        TenantResolutionMiddleware(ok)(request)
        assert request.tenant is None

    def test_nested_subdomain_rejected(self, rf, settings, acme):
        settings.TENANT_BASE_DOMAIN = "localhost"
        request = rf.get("/", HTTP_HOST="a.acme.localhost:8000")
        TenantResolutionMiddleware(ok)(request)
        assert request.tenant is None

    def test_contextvar_is_reset_after_response(self, rf, settings, acme):
        settings.TENANT_BASE_DOMAIN = "localhost"
        TenantResolutionMiddleware(ok)(rf.get("/", HTTP_HOST="acme.localhost:8000"))
        assert get_current_tenant() is None

    def test_contextvar_is_reset_when_view_raises(self, rf, settings, acme):
        settings.TENANT_BASE_DOMAIN = "localhost"

        def boom(_request):
            raise RuntimeError("view failure")

        with pytest.raises(RuntimeError):
            TenantResolutionMiddleware(boom)(rf.get("/", HTTP_HOST="acme.localhost:8000"))

        assert get_current_tenant() is None
