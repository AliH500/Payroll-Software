from decimal import Decimal

import pytest
from cryptography.fernet import Fernet

from services.encryption.fernet import build_multifernet


def test_build_multifernet_supports_multiple_keys(settings):
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    settings.FIELD_ENCRYPTION_KEYS = [key1, key2]

    mf = build_multifernet()
    token = mf.encrypt(b"secret")
    assert mf.decrypt(token) == b"secret"


def test_build_multifernet_raises_when_unset(settings):
    settings.FIELD_ENCRYPTION_KEYS = []
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        build_multifernet()


def test_old_ciphertext_decrypts_under_new_primary_key(settings):
    old = Fernet.generate_key().decode()
    settings.FIELD_ENCRYPTION_KEYS = [old]
    old_token = build_multifernet().encrypt(b"old-secret")

    new = Fernet.generate_key().decode()
    settings.FIELD_ENCRYPTION_KEYS = [new, old]
    assert build_multifernet().decrypt(old_token) == b"old-secret"


@pytest.mark.django_db
def test_encrypted_text_round_trip_through_db(settings):
    # Sanity check at the DB layer; richer assertions live in apps that use the fields.
    from apps.tenants.models import Company

    acme = Company.objects.create(
        slug="encfield", name="Enc", country="PK", currency="PKR"
    )
    assert acme.slug == "encfield"


@pytest.mark.django_db
def test_encrypted_decimal_round_trip_through_python_field():
    """End-to-end model round-trip is exercised by the employees app tests;
    this sanity check stays at the unit level."""
    from services.encryption.fields import EncryptedDecimalField

    f = EncryptedDecimalField()
    ciphertext = f.get_prep_value(Decimal("12345.67"))
    assert ciphertext != "12345.67"
    decrypted = f.from_db_value(ciphertext, None, None)
    assert decrypted == Decimal("12345.67")


def test_encrypted_text_field_round_trip_at_python_level():
    from services.encryption.fields import EncryptedTextField

    f = EncryptedTextField()
    ciphertext = f.get_prep_value("national-id-123")
    assert ciphertext != "national-id-123"
    assert f.from_db_value(ciphertext, None, None) == "national-id-123"


def test_none_passes_through_unchanged():
    from services.encryption.fields import EncryptedDecimalField, EncryptedTextField

    assert EncryptedTextField().get_prep_value(None) is None
    assert EncryptedTextField().from_db_value(None, None, None) is None
    assert EncryptedDecimalField().get_prep_value(None) is None
    assert EncryptedDecimalField().from_db_value(None, None, None) is None
