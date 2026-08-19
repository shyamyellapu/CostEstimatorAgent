import time
import uuid

import jwt

from app.config import settings


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _register_and_login(client):
    email = f"{unique('jwt')}@example.com"
    client.post("/api/auth/register", json={
        "email": email, "username": unique("jwtuser"), "full_name": "JWT User", "password": "Str0ng!Passw0rd",
    })
    login = client.post("/api/auth/login", json={"identifier": email, "password": "Str0ng!Passw0rd"})
    assert login.status_code == 200
    return login.json()["access_token"], login.cookies.get("cost_estimator_refresh")


def test_access_protected_endpoint_with_valid_token(client):
    token, _ = _register_and_login(client)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_access_without_token_rejected(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def _base_payload(**overrides):
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()), "email": "x@example.com", "role": "user", "permissions": [],
        "session_id": str(uuid.uuid4()), "token_type": "access", "jti": str(uuid.uuid4()),
        "iat": now, "nbf": now, "exp": now + 900,
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
    }
    payload.update(overrides)
    return payload


def test_expired_access_token_rejected(client):
    payload = _base_payload(exp=int(time.time()) - 10, iat=int(time.time()) - 1000, nbf=int(time.time()) - 1000)
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"


def test_tampered_access_token_rejected(client):
    token, _ = _register_and_login(client)
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_invalid_signature_rejected(client):
    payload = _base_payload()
    token = jwt.encode(payload, "a-completely-different-secret-key-value", algorithm=settings.jwt_algorithm)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_incorrect_issuer_rejected(client):
    payload = _base_payload(iss="not-the-real-issuer")
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_incorrect_audience_rejected(client):
    payload = _base_payload(aud="not-the-real-audience")
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_refresh_token_rejected_as_access_token(client):
    """An opaque refresh-token string is not a JWT, so it must fail access-token validation."""
    _, refresh_cookie = _register_and_login(client)
    assert refresh_cookie
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh_cookie}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_access_token_rejected_as_refresh_token(client):
    """A valid access-token JWT presented as the refresh cookie must be rejected — its SHA-256
    hash will never match a stored refresh_tokens.token_hash row."""
    token, _ = _register_and_login(client)
    client.cookies.set("cost_estimator_refresh", token, path="/api/auth")
    resp = client.post("/api/auth/refresh", headers={"X-CSRF-Token": "irrelevant-mismatch"})
    assert resp.status_code in (401, 403)
    client.cookies.clear()
