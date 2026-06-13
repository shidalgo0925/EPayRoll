from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx

from epayroll.auth.jwt import AuthError
from epayroll.auth.settings import AuthSettings


def sso_config_payload(settings: AuthSettings, app_base_url: str | None = None) -> dict[str, Any]:
    redirect = settings.en1_redirect_uri
    if not redirect and app_base_url:
        redirect = f"{app_base_url.rstrip('/')}/app/"
    return {
        "enabled": settings.sso_enabled,
        "authorize_url": settings.en1_authorize_url,
        "token_url": settings.en1_token_url,
        "client_id": settings.en1_client_id,
        "redirect_uri": redirect,
        "scopes": settings.en1_scopes,
    }


def build_authorize_url(settings: AuthSettings, *, state: str, redirect_uri: str | None = None) -> str:
    if not settings.sso_enabled:
        raise AuthError("SSO EN1 no configurado")
    redirect = redirect_uri or settings.en1_redirect_uri
    if not redirect:
        raise AuthError("redirect_uri requerido")
    params = {
        "response_type": "code",
        "client_id": settings.en1_client_id,
        "redirect_uri": redirect,
        "state": state,
        "scope": settings.en1_scopes,
    }
    sep = "&" if "?" in settings.en1_authorize_url else "?"
    return f"{settings.en1_authorize_url}{sep}{urlencode(params)}"


def exchange_code(code: str, settings: AuthSettings, redirect_uri: str | None = None) -> dict[str, Any]:
    if not settings.sso_enabled:
        raise AuthError("SSO EN1 no configurado")
    if not settings.en1_client_secret:
        raise AuthError("EPAYROLL_EN1_CLIENT_SECRET requerido para intercambio de código")

    redirect = redirect_uri or settings.en1_redirect_uri
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect,
        "client_id": settings.en1_client_id,
        "client_secret": settings.en1_client_secret,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(settings.en1_token_url, data=data)
    except httpx.HTTPError as e:
        raise AuthError(f"Error conectando token EN1: {e}") from e

    if resp.status_code >= 400:
        raise AuthError(f"Token EN1 rechazado ({resp.status_code}): {resp.text[:200]}")

    payload = resp.json()
    if not payload.get("access_token"):
        raise AuthError("Respuesta EN1 sin access_token")
    return payload


def refresh_tokens(refresh_token: str, settings: AuthSettings) -> dict[str, Any]:
    if not settings.en1_token_url or not settings.en1_client_id:
        raise AuthError("SSO EN1 no configurado")
    if not settings.en1_client_secret:
        raise AuthError("EPAYROLL_EN1_CLIENT_SECRET requerido")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.en1_client_id,
        "client_secret": settings.en1_client_secret,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(settings.en1_token_url, data=data)
    if resp.status_code >= 400:
        raise AuthError(f"Refresh EN1 rechazado ({resp.status_code})")
    payload = resp.json()
    if not payload.get("access_token"):
        raise AuthError("Respuesta refresh sin access_token")
    return payload


def default_app_base_url() -> str | None:
    return os.environ.get("EPAYROLL_PUBLIC_URL") or None
