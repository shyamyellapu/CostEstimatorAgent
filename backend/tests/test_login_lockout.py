import uuid

from tests.conftest import create_user


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _register(client, password="Str0ng!Passw0rd"):
    email = f"{unique('login')}@example.com"
    username = unique("loginuser")
    resp = client.post("/api/auth/register", json={
        "email": email, "username": username, "full_name": "Login User", "password": password,
    })
    assert resp.status_code == 201
    return email, username


def test_login_success(client):
    email, username = _register(client)
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "Str0ng!Passw0rd"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["user"]["username"] == username
    # Refresh token must never appear in the JSON body — only as an HttpOnly cookie.
    assert "refresh_token" not in body
    assert "cost_estimator_refresh" in resp.cookies


def test_login_invalid_credentials(client):
    email, _ = _register(client)
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "WrongPassword1!"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


def test_login_unknown_user_generic_message(client):
    resp = client.post("/api/auth/login", json={"identifier": f"{unique('ghost')}@example.com", "password": "whatever123!A"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


def test_account_lockout_after_max_attempts(client):
    email, _ = _register(client)
    for _ in range(5):
        resp = client.post("/api/auth/login", json={"identifier": email, "password": "WrongPassword1!"})
    # The 5th failure should trigger the lockout.
    assert resp.status_code == 423
    assert resp.json()["error"]["code"] == "AUTH_ACCOUNT_LOCKED"

    # Even the correct password is rejected while locked (reset the per-IP login rate-limit bucket
    # first so this assertion tests lockout behavior, not the separate rate limiter).
    from app.core.rate_limit import rate_limiter
    rate_limiter._hits.clear()
    locked_resp = client.post("/api/auth/login", json={"identifier": email, "password": "Str0ng!Passw0rd"})
    assert locked_resp.status_code == 423


def test_disabled_user_login_rejected(client):
    email = f"{unique('disabled')}@example.com"
    username = unique("disableduser")
    create_user(email, username, "Str0ng!Passw0rd", "user", is_active=False)
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "Str0ng!Passw0rd"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_ACCOUNT_DISABLED"
