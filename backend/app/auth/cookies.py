"""Helpers for setting/clearing the HttpOnly refresh-token cookie and the readable CSRF cookie."""
from datetime import timedelta

from fastapi import Response

from app.auth.csrf import generate_csrf_token
from app.config import settings


def _samesite() -> str:
    value = settings.cookie_samesite.lower()
    return value if value in ("lax", "strict", "none") else "lax"


def set_auth_cookies(response: Response, *, refresh_token: str) -> None:
    max_age = int(timedelta(days=settings.refresh_token_expire_days).total_seconds())

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=max_age,
        path=settings.cookie_path,
        domain=settings.cookie_domain or None,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=_samesite(),
    )
    # CSRF cookie must be readable by frontend JS — NOT HttpOnly. Scoped to "/" so the SPA can
    # read it regardless of which route it navigates to.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=generate_csrf_token(),
        max_age=max_age,
        path="/",
        domain=settings.cookie_domain or None,
        secure=settings.cookie_secure,
        httponly=False,
        samesite=_samesite(),
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=settings.refresh_cookie_name, path=settings.cookie_path, domain=settings.cookie_domain or None)
    response.delete_cookie(key=settings.csrf_cookie_name, path="/", domain=settings.cookie_domain or None)
