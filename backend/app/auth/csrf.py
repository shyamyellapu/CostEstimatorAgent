"""Double-submit CSRF protection for cookie-authenticated, state-changing endpoints.

HttpOnly cookies alone do NOT prevent CSRF — a browser will still attach cookies to a
cross-site form submission or fetch. We mitigate this with the double-submit pattern:

1. A non-HttpOnly `csrf_cookie_name` cookie holding a random token is set on login/refresh so
   frontend JS can read it.
2. The frontend echoes that value back in the `X-CSRF-Token` request header on state-changing
   requests.
3. The server verifies the header matches the cookie. A cross-site attacker can trigger the
   cookie to be sent automatically, but cannot read the cookie value to set the matching header
   (same-origin policy), so the two won't match.
"""
import secrets

from fastapi import Request

from app.config import settings
from app.core.exceptions import csrf_invalid

CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request) -> None:
    cookie_value = request.cookies.get(settings.csrf_cookie_name)
    header_value = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_value or not header_value or not secrets.compare_digest(cookie_value, header_value):
        raise csrf_invalid()
