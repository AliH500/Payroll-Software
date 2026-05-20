"""Post-save / post-delete hooks that record audit entries for registered models.

Models opt-in by adding themselves to AUDITED_MODELS at import time
(typically in their app's apps.py ready() hook).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.audit.models import AuditAction
from apps.audit.recorders import record_audit

AUDITED_MODELS: set[type[Model]] = set()


def register_audit(model_cls: type[Model]) -> None:
    """Add a model to the audited set. Idempotent."""
    AUDITED_MODELS.add(model_cls)


@receiver(post_save)
def _audit_post_save(sender: type[Model], instance: Model, created: bool, **kwargs: Any) -> None:
    if sender not in AUDITED_MODELS:
        return
    record_audit(
        action=AuditAction.CREATE if created else AuditAction.UPDATE,
        target=instance,
    )


@receiver(post_delete)
def _audit_post_delete(sender: type[Model], instance: Model, **kwargs: Any) -> None:
    if sender not in AUDITED_MODELS:
        return
    record_audit(action=AuditAction.DELETE, target=instance)
