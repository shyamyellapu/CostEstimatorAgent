"""Opaque refresh-token generation and hashing.

Refresh tokens are cryptographically random, high-entropy opaque strings — never JWTs, and the
raw value is never persisted. Only the SHA-256 hash is stored in `refresh_tokens.token_hash`, so
a database compromise alone does not expose usable refresh tokens.
"""
import hashlib
import secrets

TOKEN_BYTES = 32  # 256 bits of entropy


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
