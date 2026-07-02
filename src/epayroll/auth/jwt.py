from __future__ import annotations

from typing import Any

from epayroll.auth.context import AuthContext
from epayroll.auth.settings import AuthSettings


class AuthError(Exception):
    pass


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Authorization debe ser Bearer <token>")
    token = parts[1].strip()
    if not token:
        raise AuthError("Token vacío")
    return token


def decode_jwt(token: str, settings: AuthSettings) -> AuthContext:
    try:
        import jwt
    except ImportError as e:
        raise AuthError("PyJWT no instalado — pip install PyJWT") from e

    options: dict[str, bool] = {"require": ["exp", "sub", "tenant_id"]}
    decode_kwargs: dict[str, Any] = {
        "algorithms": [settings.jwt_algorithm],
        "options": options,
    }
    if settings.jwt_audience:
        decode_kwargs["audience"] = settings.jwt_audience
    if settings.jwt_issuer:
        decode_kwargs["issuer"] = settings.jwt_issuer

    try:
        payload = jwt.decode(token, settings.jwt_secret, **decode_kwargs)
    except jwt.PyJWTError as e:
        raise AuthError(f"Token inválido: {e}") from e

    tenant_id = str(payload.get("tenant_id") or "")
    if not tenant_id:
        raise AuthError("Claim tenant_id requerido")

    org_id = payload.get("organization_id")
    roles_raw = payload.get("roles") or payload.get("role") or []
    if isinstance(roles_raw, str):
        roles = tuple(r.strip() for r in roles_raw.split(",") if r.strip())
    else:
        roles = tuple(str(r) for r in roles_raw)

    return AuthContext(
        tenant_id=tenant_id,
        user_id=str(payload.get("sub")) if payload.get("sub") else None,
        organization_id=str(org_id) if org_id else None,
        roles=roles,
        is_superuser=bool(payload.get("is_superuser")),
    )


def encode_jwt(
    *,
    tenant_id: str,
    user_id: str,
    organization_id: str | None = None,
    roles: list[str] | None = None,
    is_superuser: bool = False,
    settings: AuthSettings | None = None,
    expires_hours: int = 8,
) -> str:
    try:
        import jwt
    except ImportError as e:
        raise AuthError("PyJWT no instalado") from e

    from datetime import UTC, datetime, timedelta

    from epayroll.auth.settings import get_auth_settings

    settings = settings or get_auth_settings()

    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": datetime.now(tz=UTC) + timedelta(hours=expires_hours),
    }
    if organization_id:
        payload["organization_id"] = organization_id
    if roles:
        payload["roles"] = roles
    if is_superuser:
        payload["is_superuser"] = True
    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience
    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

