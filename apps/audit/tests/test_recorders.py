import pytest

from apps.accounts.context import user_context
from apps.accounts.models import Role, User
from apps.audit.models import AuditAction, AuditLogEntry
from apps.audit.recorders import record_audit
from apps.tenants.context import tenant_context
from apps.tenants.models import Company


@pytest.fixture
def acme(db) -> Company:
    return Company.objects.create(slug="acme", name="Acme", country="PK", currency="PKR")


@pytest.fixture
def alice(acme) -> User:
    return User.objects.create_user(
        email="alice@acme.local",
        password="x",
        company=acme,
        role=Role.COMPANY_ADMIN,
    )


@pytest.mark.django_db
def test_record_audit_without_tenant_is_silent(acme, alice):
    # No tenant_context -> return None, no row written.
    with user_context(alice):
        assert record_audit(action=AuditAction.CREATE, target=acme) is None
    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
def test_record_audit_inside_tenant_creates_entry(acme, alice):
    with tenant_context(acme), user_context(alice):
        entry = record_audit(action=AuditAction.CREATE, target=acme, metadata={"note": "seeded"})
    assert entry is not None
    assert entry.company == acme
    assert entry.actor == alice
    assert entry.action == AuditAction.CREATE
    assert entry.target_model == "tenants.Company"
    assert entry.target_id == str(acme.pk)
    assert entry.metadata == {"note": "seeded"}


@pytest.mark.django_db
def test_record_audit_with_no_actor_records_null(acme):
    with tenant_context(acme):
        entry = record_audit(action=AuditAction.UPDATE, target=acme)
    assert entry is not None
    assert entry.actor is None
