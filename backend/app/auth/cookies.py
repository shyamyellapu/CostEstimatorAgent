"""Helpers for setting/clearing the HttpOnly refresh-token cookie and the readable CSRF cookie."""
from datetime import timedelta

from fastapi import Response

from app.auth.csrf import generate_csrf_token
from app.config import settings


def _samesite() -> str:
    value = settings.cookie_samesite.lower()
    return value if value in ("lax", "strict", "none") else "lax"


def set_auth_cookies(response: Response, *, refresh_token: str) -> str:
    """Set the refresh + CSRF cookies and return the CSRF token value.

    The CSRF cookie is also returned directly so callers can echo it in the JSON
    response body: when frontend and backend are on different registrable domains
    (e.g. an *.azurestaticapps.net SPA calling an *.azurewebsites.net API), a
    cookie set by the backend's response is scoped to the backend's own host —
    frontend JS running on the SPA's origin can never read it via `document.cookie`.
    Handing the value back in the body lets the frontend cache it in memory instead.
    """
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
    # read it regardless of which route it navigates to. Kept for same-origin/local-dev setups.
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        path="/",
        domain=settings.cookie_domain or None,
        secure=settings.cookie_secure,
        httponly=False,
        samesite=_samesite(),
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=settings.refresh_cookie_name, path=settings.cookie_path, domain=settings.cookie_domain or None)
    response.delete_cookie(key=settings.csrf_cookie_name, path="/", domain=settings.cookie_domain or None)
