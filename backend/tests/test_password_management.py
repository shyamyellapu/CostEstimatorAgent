import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

from tests.conftest import run_async
from tests.helpers import auth_headers, csrf_headers, register_and_login, unique


def test_change_password_requires_current_password(client):
    _, _, access_token = register_and_login(client)
    resp = client.post("/api/auth/change-password", headers={**auth_headers(access_token), **csrf_headers(client)}, json={
        "current_password": "WrongCurrent1!", "new_password": "NewStr0ng!Pass1",
    })
    assert resp.status_code == 401


def test_change_password_success_and_old_password_rejected(client):
    email, _, access_token = register_and_login(client)
    resp = client.post("/api/auth/change-password", headers={**auth_headers(access_token), **csrf_headers(client)}, json={
        "current_password": "Str0ng!Passw0rd", "new_password": "NewStr0ng!Pass1",
    })
    assert resp.status_code == 204

    old_login = client.post("/api/auth/login", json={"identifier": email, "password": "Str0ng!Passw0rd"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"identifier": email, "password": "NewStr0ng!Pass1"})
    assert new_login.status_code == 200


def test_forgot_password_generic_response_for_any_email(client):
    resp = client.post("/api/auth/forgot-password", json={"email": f"{unique('nobody')}@example.com"})
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_password_reset_full_flow(client):
    email, _, _ = register_and_login(client)
    fixed_token = "fixed-reset-token-for-tests"

    with patch("app.services.password_reset_service.secrets.token_urlsafe", return_value=fixed_token):
        req = client.post("/api/auth/forgot-password", json={"email": email})
        assert req.status_code == 200

    reset = client.post("/api/auth/reset-password", json={"token": fixed_token, "new_password": "ResetStr0ng!Pass1"})
    assert reset.status_code == 200

    old_login = client.post("/api/auth/login", json={"identifier": email, "password": "Str0ng!Passw0rd"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login", json={"identifier": email, "password": "ResetStr0ng!Pass1"})
    assert new_login.status_code == 200


def test_used_reset_token_rejected(client):
    email, _, _ = register_and_login(client)
    fixed_token = "one-time-only-token"
    with patch("app.services.password_reset_service.secrets.token_urlsafe", return_value=fixed_token):
        client.post("/api/auth/forgot-password", json={"email": email})

    first = client.post("/api/auth/reset-password", json={"token": fixed_token, "new_password": "FirstUseStr0ng!1"})
    assert first.status_code == 200

    second = client.post("/api/auth/reset-password", json={"token": fixed_token, "new_password": "SecondUseStr0ng!1"})
    assert second.status_code == 400


async def _insert_expired_reset_token(user_email: str, raw_token: str):
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models import PasswordResetToken, User

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == user_email))).scalar_one()
        db.add(PasswordResetToken(
            user_id=user.id, token_hash=token_hash,
            expires_at=datetime.utcnow() - timedelta(minutes=5),
        ))
        await db.commit()


def test_expired_reset_token_rejected(client):
    email, _, _ = register_and_login(client)
    raw_token = "already-expired-token"
    run_async(_insert_expired_reset_token(email, raw_token))

    resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "WhateverStr0ng!1"})
    assert resp.status_code == 400
