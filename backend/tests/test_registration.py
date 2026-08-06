import uuid

from tests.conftest import create_user


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def test_registration_success(client):
    email = f"{unique('reg')}@example.com"
    resp = client.post("/api/auth/register", json={
        "email": email, "username": unique("reguser"), "full_name": "Reg User",
        "password": "Str0ng!Passw0rd",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == email
    assert body["role"] == "user"  # default public self-registration role
    assert "hashed_password" not in body
    assert "permissions" in body


def test_registration_duplicate_email(client):
    email = f"{unique('dup')}@example.com"
    payload = {"email": email, "username": unique("dupuser"), "full_name": "Dup User", "password": "Str0ng!Passw0rd"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    payload["username"] = unique("dupuser2")
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "AUTH_EMAIL_ALREADY_EXISTS"


def test_registration_duplicate_username(client):
    username = unique("sameuser")
    payload = {"email": f"{unique('a')}@example.com", "username": username, "full_name": "A", "password": "Str0ng!Passw0rd"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    payload["email"] = f"{unique('b')}@example.com"
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "AUTH_USERNAME_ALREADY_EXISTS"


def test_registration_weak_password_rejected(client):
    resp = client.post("/api/auth/register", json={
        "email": f"{unique('weak')}@example.com", "username": unique("weakuser"),
        "full_name": "Weak Pw", "password": "weak",
    })
    assert resp.status_code in (422, 400)


def test_registration_cannot_self_assign_admin_role(client):
    """requested_role is accepted for UX but never trusted — server always assigns the default."""
    email = f"{unique('noadmin')}@example.com"
    resp = client.post("/api/auth/register", json={
        "email": email, "username": unique("noadminuser"), "full_name": "No Admin",
        "password": "Str0ng!Passw0rd", "requested_role": "admin",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] != "admin"
