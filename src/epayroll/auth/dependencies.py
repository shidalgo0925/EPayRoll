from __future__ import annotations

from starlette.requests import Request

from epayroll.auth.context import AuthContext


def get_auth_context(request: Request) -> AuthContext:
    return getattr(request.state, "auth", AuthContext.anonymous())
