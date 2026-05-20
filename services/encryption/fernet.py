"""Build a MultiFernet from settings.FIELD_ENCRYPTION_KEYS.

MultiFernet lets us rotate keys: list the newest key first; older ciphertext
encrypted with previous keys still decrypts.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def build_multifernet() -> MultiFernet:
    keys = getattr(settings, "FIELD_ENCRYPTION_KEYS", None)
    if not keys:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEYS must be set to a non-empty list of Fernet keys. "
            "Generate one with: make generate-key"
        )
    fernets: list[Fernet] = []
    for key in keys:
        material = key.encode() if isinstance(key, str) else key
        fernets.append(Fernet(material))
    return MultiFernet(fernets)
