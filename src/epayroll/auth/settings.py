from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AuthSettings:
    mode: str  # disabled | stub | jwt | en1
    jwt_secret: str
    jwt_algorithm: str
    jwt_audience: str | None
    jwt_issuer: str | None
    jwt_expires_hours: int
    en1_jwks_url: str | None
    en1_authorize_url: str | None
    en1_token_url: str | None
    en1_client_id: str | None
    en1_client_secret: str | None
    en1_redirect_uri: str | None
    en1_scopes: str

    @property
    def enabled(self) -> bool:
        return self.mode not in ("disabled", "off", "none", "")

    @property
    def sso_enabled(self) -> bool:
        return bool(self.en1_authorize_url and self.en1_token_url and self.en1_client_id)


@lru_cache
def get_auth_settings() -> AuthSettings:
    # 0 = sin vencimiento (JWT local sin claim exp). Máx. 8760h (~1 año) si se usa TTL.
    expires_raw = os.environ.get("EPAYROLL_JWT_EXPIRES_HOURS", "0").strip()
    try:
        expires_hours = max(0, min(int(expires_raw), 8760))
    except ValueError:
        expires_hours = 0
    return AuthSettings(
        mode=os.environ.get("EPAYROLL_AUTH_MODE", "stub").strip().lower(),
        jwt_secret=os.environ.get("EPAYROLL_JWT_SECRET", "dev-change-me"),
        jwt_algorithm=os.environ.get("EPAYROLL_JWT_ALGORITHM", "HS256"),
        jwt_audience=os.environ.get("EPAYROLL_JWT_AUDIENCE") or None,
        jwt_issuer=os.environ.get("EPAYROLL_JWT_ISSUER") or None,
        jwt_expires_hours=expires_hours,
        en1_jwks_url=os.environ.get("EPAYROLL_EN1_JWKS_URL") or None,
        en1_authorize_url=os.environ.get("EPAYROLL_EN1_AUTHORIZE_URL") or None,
        en1_token_url=os.environ.get("EPAYROLL_EN1_TOKEN_URL") or None,
        en1_client_id=os.environ.get("EPAYROLL_EN1_CLIENT_ID") or None,
        en1_client_secret=os.environ.get("EPAYROLL_EN1_CLIENT_SECRET") or None,
        en1_redirect_uri=os.environ.get("EPAYROLL_EN1_REDIRECT_URI") or None,
        en1_scopes=os.environ.get("EPAYROLL_EN1_SCOPES", "openid profile email"),
    )
