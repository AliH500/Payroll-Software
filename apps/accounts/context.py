"""Request-scoped current-user binding for audit attribution.

Mirrors the tenant ContextVar pattern: middleware sets it on every request,
non-request code (background jobs, management commands) binds explicitly via
the `user_context` context manager.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User

current_user: ContextVar[User | None] = ContextVar("current_user", default=None)


def get_current_user() -> User | None:
    return current_user.get()


@contextmanager
def user_context(user: User | None) -> Iterator[None]:
    token = current_user.set(user)
    try:
        yield
    finally:
        current_user.reset(token)
