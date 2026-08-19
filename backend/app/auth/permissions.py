"""Pure RBAC helper logic shared between the JWT payload and FastAPI dependencies.

The source of truth for a role's permissions is the `role_permissions` table. To avoid a DB
round-trip on every request, the current permission set is embedded in the access token at
login/refresh time and re-computed at most every `ACCESS_TOKEN_EXPIRE_MINUTES` (15 min default).
Backend authorization dependencies always check against this token-embedded set — never trust
anything the frontend claims about its own role or permissions.
"""


def has_permission(granted: list[str], required: str) -> bool:
    return required in granted


def has_any_permission(granted: list[str], required: list[str]) -> bool:
    return any(code in granted for code in required)


def has_all_permissions(granted: list[str], required: list[str]) -> bool:
    return all(code in granted for code in required)


def has_role(role: str, required: str) -> bool:
    return role == required


def has_any_role(role: str, required: list[str]) -> bool:
    return role in required
