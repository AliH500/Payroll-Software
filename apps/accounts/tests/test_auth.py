import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.tenants.models import Company


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(slug="acme", name="Acme", country="PK", currency="PKR")


@pytest.fixture
def beta(db) -> Company:
    return Company.objects.create(slug="beta", name="Beta", country="ET", currency="ETB")


@pytest.fixture
def alice(acme) -> User:
    return User.objects.create_user(
        email="alice@acme.test",
        password="strong-password-123",
        company=acme,
        role=Role.COMPANY_ADMIN,
    )


@pytest.fixture
def super_admin(db) -> User:
    return User.objects.create_superuser(
        email="ali@platform.test",
        password="platform-pass-456",
    )


@pytest.mark.django_db
class TestLogin:
    def test_login_page_renders(self, client):
        resp = client.get(reverse("login"), HTTP_HOST="acme.localhost")
        assert resp.status_code == 200
        assert b"Sign in" in resp.content

    def test_login_succeeds_on_matching_subdomain(self, client, alice):
        resp = client.post(
            reverse("login"),
            {"username": "alice@acme.test", "password": "strong-password-123"},
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 302
        assert client.session.get("_auth_user_id") is not None

    def test_login_blocked_on_wrong_subdomain(self, client, alice, beta):
        resp = client.post(
            reverse("login"),
            {"username": "alice@acme.test", "password": "strong-password-123"},
            HTTP_HOST="beta.localhost",
        )
        assert resp.status_code == 200
        assert resp.context["form"].has_error("__all__", code="wrong_tenant")
        assert client.session.get("_auth_user_id") is None

    def test_login_blocked_on_root_for_non_super_admin(self, client, alice):
        resp = client.post(
            reverse("login"),
            {"username": "alice@acme.test", "password": "strong-password-123"},
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert client.session.get("_auth_user_id") is None

    def test_super_admin_logs_in_on_root(self, client, super_admin):
        resp = client.post(
            reverse("login"),
            {"username": "ali@platform.test", "password": "platform-pass-456"},
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 302
        assert client.session.get("_auth_user_id") is not None

    def test_super_admin_blocked_on_tenant_subdomain(self, client, super_admin, acme):
        resp = client.post(
            reverse("login"),
            {"username": "ali@platform.test", "password": "platform-pass-456"},
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 200
        assert client.session.get("_auth_user_id") is None

    def test_invalid_credentials_do_not_authenticate(self, client, alice):
        resp = client.post(
            reverse("login"),
            {"username": "alice@acme.test", "password": "wrong"},
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 200
        assert client.session.get("_auth_user_id") is None


@pytest.mark.django_db
class TestLogout:
    def test_logout_clears_session(self, client, alice):
        client.force_login(alice)
        assert client.session.get("_auth_user_id") is not None
        resp = client.post(reverse("logout"), HTTP_HOST="acme.localhost")
        assert resp.status_code == 302
        assert client.session.get("_auth_user_id") is None


@pytest.mark.django_db
class TestRateLimit:
    def test_lockout_after_repeated_failed_attempts(self, client, alice, settings):
        settings.AXES_FAILURE_LIMIT = 3
        for _ in range(3):
            client.post(
                reverse("login"),
                {"username": "alice@acme.test", "password": "wrong"},
                HTTP_HOST="acme.localhost",
            )
        resp = client.post(
            reverse("login"),
            {"username": "alice@acme.test", "password": "strong-password-123"},
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 429
        assert client.session.get("_auth_user_id") is None

    def test_successful_login_resets_failure_count(self, client, alice, settings):
        settings.AXES_FAILURE_LIMIT = 3
        settings.AXES_RESET_ON_SUCCESS = True
        for _ in range(2):
            client.post(
                reverse("login"),
                {"username": "alice@acme.test", "password": "wrong"},
                HTTP_HOST="acme.localhost",
            )
        # One good login resets the counter
        client.post(
            reverse("login"),
            {"username": "alice@acme.test", "password": "strong-password-123"},
            HTTP_HOST="acme.localhost",
        )
        client.logout()
        # Another two failures should not yet trigger a lockout
        for _ in range(2):
            resp = client.post(
                reverse("login"),
                {"username": "alice@acme.test", "password": "wrong"},
                HTTP_HOST="acme.localhost",
            )
        assert resp.status_code == 200  # still form re-render, not lockout


@pytest.mark.django_db
class TestPasswordReset:
    def test_reset_form_renders(self, client):
        resp = client.get(reverse("password_reset"), HTTP_HOST="acme.localhost")
        assert resp.status_code == 200

    def test_reset_sends_email_to_known_account(self, client, alice):
        resp = client.post(
            reverse("password_reset"),
            {"email": "alice@acme.test"},
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 302
        assert len(mail.outbox) == 1
        assert "alice@acme.test" in mail.outbox[0].to
        assert "Reset your Payroll password" in mail.outbox[0].subject

    def test_reset_does_not_reveal_unknown_account(self, client):
        resp = client.post(
            reverse("password_reset"),
            {"email": "ghost@nowhere.test"},
            HTTP_HOST="acme.localhost",
        )
        assert resp.status_code == 302
        assert len(mail.outbox) == 0
