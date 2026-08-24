from tests.helpers import auth_headers, csrf_headers, register_and_login

REFRESH_COOKIE_KW = {"path": "/api/auth"}


def test_refresh_success_rotates_token(client):
    email, username, access_token = register_and_login(client)
    old_refresh = client.cookies.get("cost_estimator_refresh", **REFRESH_COOKIE_KW)
    assert old_refresh

    resp = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["username"] == username

    new_refresh = client.cookies.get("cost_estimator_refresh", **REFRESH_COOKIE_KW)
    assert new_refresh and new_refresh != old_refresh, "refresh token must rotate to a new value"


def test_old_refresh_token_rejected_after_rotation(client):
    register_and_login(client)
    old_refresh = client.cookies.get("cost_estimator_refresh", **REFRESH_COOKIE_KW)

    first = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert first.status_code == 200

    # Replay the token that was just rotated out.
    client.cookies.set("cost_estimator_refresh", old_refresh, **REFRESH_COOKIE_KW)
    second = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "AUTH_REFRESH_REUSED"


def test_refresh_reuse_revokes_entire_family(client):
    """After a replay is detected, even the token issued by the *first* (legitimate) rotation
    must be rejected — the whole token family is invalidated."""
    register_and_login(client)
    original_refresh = client.cookies.get("cost_estimator_refresh", **REFRESH_COOKIE_KW)

    first = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert first.status_code == 200
    rotated_refresh = client.cookies.get("cost_estimator_refresh", **REFRESH_COOKIE_KW)

    # Replay the original (now-revoked) token -> triggers family-wide revocation.
    client.cookies.set("cost_estimator_refresh", original_refresh, **REFRESH_COOKIE_KW)
    reuse_resp = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error"]["code"] == "AUTH_REFRESH_REUSED"

    # The legitimately-rotated token (child of the same family) must now also be dead.
    client.cookies.set("cost_estimator_refresh", rotated_refresh, **REFRESH_COOKIE_KW)
    after_reuse = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert after_reuse.status_code == 401


def test_revoked_session_blocks_access_token_immediately(client):
    """logout revokes the session; even a still-unexpired access token must be rejected on the
    very next authenticated request because get_current_user checks session status live."""
    _, _, access_token = register_and_login(client)
    logout_resp = client.post("/api/auth/logout", headers={**auth_headers(access_token), **csrf_headers(client)})
    assert logout_resp.status_code == 204

    me_resp = client.get("/api/auth/me", headers=auth_headers(access_token))
    assert me_resp.status_code == 401
    assert me_resp.json()["error"]["code"] == "AUTH_SESSION_REVOKED"
