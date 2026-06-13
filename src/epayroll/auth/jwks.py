from __future__ import annotations

from functools import lru_cache
from typing import Any

from epayroll.auth.context import AuthContext
from epayroll.auth.jwt import AuthError
from epayroll.auth.settings import AuthSettings


def _payload_to_context(payload: dict[str, Any]) -> AuthContext:
    tenant_id = str(payload.get("tenant_id") or payload.get("tenantId") or "")
    if not tenant_id:
        raise AuthError("Claim tenant_id requerido")

    org_id = payload.get("organization_id") or payload.get("organizationId")
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
    )


@lru_cache
def _jwk_client(jwks_url: str):
    try:
        import jwt
    except ImportError as e:
        raise AuthError("PyJWT no instalado") from e
    return jwt.PyJWKClient(jwks_url)


def decode_en1_jwt(token: str, settings: AuthSettings) -> AuthContext:
    """Valida JWT emitido por EN1 vía JWKS (RS256/ES256)."""
    if not settings.en1_jwks_url:
        raise AuthError("EPAYROLL_EN1_JWKS_URL requerido en modo en1")

    try:
        import jwt
    except ImportError as e:
        raise AuthError("PyJWT no instalado") from e

    client = _jwk_client(settings.en1_jwks_url)
    try:
        signing_key = client.get_signing_key_from_jwt(token)
    except jwt.PyJWTError as e:
        raise AuthError(f"No se pudo resolver clave JWKS: {e}") from e

    algorithms = list(dict.fromkeys(["RS256", "ES256", settings.jwt_algorithm]))
    decode_kwargs: dict[str, Any] = {
        "algorithms": algorithms,
        "options": {"require": ["exp", "sub"]},
    }
    if settings.jwt_audience:
        decode_kwargs["audience"] = settings.jwt_audience
    if settings.jwt_issuer:
        decode_kwargs["issuer"] = settings.jwt_issuer

    try:
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
    except jwt.PyJWTError as e:
        raise AuthError(f"Token EN1 inválido: {e}") from e

    return _payload_to_context(payload)
