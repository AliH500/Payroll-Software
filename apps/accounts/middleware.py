from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.accounts.context import current_user


class UserContextMiddleware:
    """Bind `request.user` (if authenticated) to the current_user ContextVar.

    Runs after AuthenticationMiddleware. Anonymous users bind None, which audit
    recorders interpret as 'system-initiated' or 'pre-auth'.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        candidate = getattr(request, "user", None)
        user = candidate if candidate and candidate.is_authenticated else None
        token = current_user.set(user)
        try:
            return self.get_response(request)
        finally:
            current_user.reset(token)
