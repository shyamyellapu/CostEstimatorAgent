"""JWT access-token issuance and verification.

Refresh tokens are NOT JWTs — see `app.auth.refresh_tokens` for the opaque, high-entropy,
hash-stored refresh-token design. Only short-lived access tokens are signed JWTs.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from app.config import settings
from app.core.exceptions import token_expired, token_invalid

ACCESS_TOKEN_TYPE = "access"


def create_access_token(
    *,
    user_id: str,
    email: str,
    role: str,
    permissions: list[str],
    session_id: str,
) -> tuple[str, int, str]:
    """Returns (token, expires_in_seconds, jti)."""
    now = datetime.now(timezone.utc)
    expire_delta = timedelta(minutes=settings.access_token_expire_minutes)
    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "permissions": permissions,
        "session_id": str(session_id),
        "token_type": ACCESS_TOKEN_TYPE,
        "jti": jti,
        "iat": now,
        "nbf": now,
        "exp": now + expire_delta,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expire_delta.total_seconds()), jti


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and structurally validate an access-token JWT.

    Validates signature, expiration, not-before, issuer, audience, and token_type.
    Does NOT check user/session status in the database — callers (FastAPI dependencies) must
    do that separately so a token can be rejected the moment a session is revoked or a user is
    disabled, even if the JWT itself has not expired yet.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "nbf", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise token_expired()
    except jwt.PyJWTError:
        # Covers: invalid signature, tampered payload, wrong issuer/audience, malformed token
        raise token_invalid()

    if payload.get("token_type") != ACCESS_TOKEN_TYPE:
        # Prevents a refresh token (or any other token type) from being used as an access token
        raise token_invalid()

    return payload
