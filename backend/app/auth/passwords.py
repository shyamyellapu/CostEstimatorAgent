"""Password hashing and policy enforcement.

Uses Argon2id via pwdlib (preferred, memory-hard, resistant to GPU cracking).
"""
import re

from pwdlib import PasswordHash

from app.core.exceptions import AppError

_password_hash = PasswordHash.recommended()  # Argon2id with secure defaults

COMMON_PASSWORDS = {
    "password", "password1", "12345678", "qwerty123", "letmein123",
    "admin123", "welcome123", "changeme", "password123", "123456789",
}

MIN_LENGTH = 8
MAX_LENGTH = 128


def hash_password(plain_password: str) -> str:
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False


def validate_password_policy(password: str, *, email: str | None = None, username: str | None = None) -> None:
    """Enforce the password policy. Raises AppError(AUTH_PASSWORD_POLICY_FAILED) on failure."""
    errors: list[str] = []

    if len(password) < MIN_LENGTH:
        errors.append(f"Password must be at least {MIN_LENGTH} characters long.")
    if len(password) > MAX_LENGTH:
        errors.append(f"Password must not exceed {MAX_LENGTH} characters.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain an uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain a lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain a number.")
    if not re.search(r"[^\w\s]", password):
        errors.append("Password must contain a special character.")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common. Choose a stronger password.")

    lowered = password.lower()
    if email and email.split("@")[0].lower() in lowered:
        errors.append("Password must not contain your email address.")
    if username and username.lower() in lowered:
        errors.append("Password must not contain your username.")

    if errors:
        raise AppError(
            code="AUTH_PASSWORD_POLICY_FAILED",
            message=" ".join(errors),
            status_code=422,
        )
