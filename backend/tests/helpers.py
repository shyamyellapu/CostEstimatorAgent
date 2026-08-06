"""Shared helpers for HTTP-level auth tests."""
import uuid

REFRESH_COOKIE = "cost_estimator_refresh"
CSRF_COOKIE = "cost_estimator_csrf"


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def register(client, password: str = "Str0ng!Passw0rd") -> tuple[str, str]:
    email = f"{unique('u')}@example.com"
    username = unique("user")
    resp = client.post("/api/auth/register", json={
        "email": email, "username": username, "full_name": "Test User", "password": password,
    })
    assert resp.status_code == 201, resp.text
    return email, username


def login(client, email: str, password: str = "Str0ng!Passw0rd"):
    resp = client.post("/api/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp


def register_and_login(client, password: str = "Str0ng!Passw0rd"):
    email, username = register(client, password)
    resp = login(client, email, password)
    return email, username, resp.json()["access_token"]


def csrf_headers(client) -> dict:
    token = client.cookies.get(CSRF_COOKIE)
    return {"X-CSRF-Token": token} if token else {}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
