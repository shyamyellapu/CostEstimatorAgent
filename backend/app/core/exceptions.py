"""Application-wide exception types and the consistent error response schema.

All authentication/authorization failures should raise `AppError` (or a subclass) so the
global exception handler in `app.main` can translate it into the standard envelope:

    {"error": {"code": "AUTH_INVALID_CREDENTIALS", "message": "...", "request_id": "..."}}

Never leak internal exception details (DB errors, stack traces) to the client.
"""
from typing import Any, Optional


class AppError(Exception):
    """Base application error carrying an HTTP status code and a stable machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int = 400, headers: Optional[dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}
        super().__init__(message)


class AuthError(AppError):
    """Authentication/authorization specific error. Defaults to 401."""

    def __init__(self, code: str, message: str, status_code: int = 401, headers: Optional[dict[str, Any]] = None):
        super().__init__(code=code, message=message, status_code=status_code, headers=headers)


# ─── Common, pre-defined auth errors (generic messages — no account enumeration) ──────────────

def invalid_credentials() -> AuthError:
    return AuthError("AUTH_INVALID_CREDENTIALS", "Invalid email/username or password.", 401)


def account_locked() -> AuthError:
    return AuthError("AUTH_ACCOUNT_LOCKED", "This account is temporarily locked due to repeated failed sign-in attempts.", 423)


def account_disabled() -> AuthError:
    return AuthError("AUTH_ACCOUNT_DISABLED", "This account has been disabled. Contact an administrator.", 403)


def token_expired() -> AuthError:
    return AuthError("AUTH_TOKEN_EXPIRED", "Session expired. Please sign in again.", 401)


def token_invalid() -> AuthError:
    return AuthError("AUTH_TOKEN_INVALID", "Invalid authentication token.", 401)


def refresh_invalid() -> AuthError:
    return AuthError("AUTH_REFRESH_INVALID", "Invalid or expired refresh token.", 401)


def refresh_reused() -> AuthError:
    return AuthError("AUTH_REFRESH_REUSED", "This session was terminated for security reasons. Please sign in again.", 401)


def session_revoked() -> AuthError:
    return AuthError("AUTH_SESSION_REVOKED", "This session has been revoked. Please sign in again.", 401)


def csrf_invalid() -> AuthError:
    return AuthError("AUTH_CSRF_INVALID", "CSRF validation failed.", 403)


def permission_denied() -> AuthError:
    return AuthError("AUTH_PERMISSION_DENIED", "You do not have permission to perform this action.", 403)


def email_exists() -> AppError:
    return AppError("AUTH_EMAIL_ALREADY_EXISTS", "An account with this email already exists.", 409)


def username_exists() -> AppError:
    return AppError("AUTH_USERNAME_ALREADY_EXISTS", "This username is already taken.", 409)


def rate_limited(retry_after: int) -> AppError:
    return AppError(
        "AUTH_RATE_LIMITED",
        "Too many requests. Please try again later.",
        429,
        headers={"Retry-After": str(retry_after)},
    )
