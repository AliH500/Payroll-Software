"""Field-level Fernet encryption for sensitive columns.

Storage: ciphertext as TEXT. The plaintext is exposed on the Python side via the
field's `from_db_value` / `get_prep_value`. Exact-match equality against ciphertext
is not useful (each encryption produces a different ciphertext), so these fields
are not suitable for filtering or unique constraints. Use them only on attributes
that are read-decrypted-then-used in Python code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms
from django.db import models

from services.encryption.fernet import build_multifernet


def _encrypt(plaintext: str) -> str:
    return build_multifernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    return build_multifernet().decrypt(ciphertext.encode()).decode()


class EncryptedTextField(models.TextField):  # type: ignore[type-arg]
    """TEXT column whose value is encrypted at rest with Fernet.

    Rendered in forms as a single-line input (not a Textarea) since the values
    are identifiers, not long-form text.
    """

    description = "Fernet-encrypted text"

    def get_prep_value(self, value: Any) -> Any:
        if value is None:
            return None
        return _encrypt(str(value))

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        if value is None:
            return None
        return _decrypt(value)

    def formfield(self, **kwargs: Any) -> Any:  # type: ignore[override]
        defaults: dict[str, Any] = {
            "widget": forms.TextInput(),
            "required": not self.blank,
            "max_length": 200,
        }
        defaults.update(kwargs)
        return forms.CharField(**defaults)


class EncryptedDecimalField(models.TextField):  # type: ignore[type-arg]
    """Decimal stored as encrypted TEXT.

    SQL aggregate / sort / comparison against this column is impossible by design
    (the ciphertext is opaque). Read rows into Python and compute there. Use the
    `domain.Money` value type for any aggregation or display.

    Forms render this as a numeric input with two-decimal step. Validation is
    handled by forms.DecimalField at the form layer.
    """

    description = "Fernet-encrypted Decimal"

    def get_prep_value(self, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return _encrypt(str(value))

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        if value is None:
            return None
        return Decimal(_decrypt(value))

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def formfield(self, **kwargs: Any) -> Any:  # type: ignore[override]
        defaults: dict[str, Any] = {
            "max_digits": 14,
            "decimal_places": 2,
            "widget": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "required": not self.blank,
        }
        defaults.update(kwargs)
        return forms.DecimalField(**defaults)
