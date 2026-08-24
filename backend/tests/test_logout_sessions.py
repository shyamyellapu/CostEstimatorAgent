from tests.helpers import auth_headers, csrf_headers, login, register, register_and_login


def test_logout_current_session(client):
    _, _, access_token = register_and_login(client)
    resp = client.post("/api/auth/logout", headers={**auth_headers(access_token), **csrf_headers(client)})
    assert resp.status_code == 204
    # Refresh cookie must be cleared client-side too.
    assert client.cookies.get("cost_estimator_refresh") in (None, "")


def test_logout_all_revokes_every_session(client):
    email, username = register(client)
    login(client, email)
    token_a = client.cookies.get("cost_estimator_refresh", path="/api/auth")

    # Simulate a second device/session with its own login.
    login_b = login(client, email)
    access_b = login_b.json()["access_token"]

    logout_all = client.post("/api/auth/logout-all", headers={**auth_headers(access_b), **csrf_headers(client)})
    assert logout_all.status_code == 204

    # logout-all's response clears the CSRF cookie too, so set a fresh self-consistent
    # cookie/header pair here — double-submit CSRF only requires the two to match, not any
    # specific prior value. This isolates the assertion to refresh-token revocation behavior.
    client.cookies.set("cost_estimator_refresh", token_a, path="/api/auth")
    client.cookies.set("cost_estimator_csrf", "post-logout-all-csrf-check", path="/")
    refresh_a = client.post("/api/auth/refresh", headers={"X-CSRF-Token": "post-logout-all-csrf-check"})
    assert refresh_a.status_code == 401


def test_list_and_revoke_own_sessions(client):
    email, _, access_token = register_and_login(client)
    sessions_resp = client.get("/api/auth/sessions", headers=auth_headers(access_token))
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()
    assert len(sessions) >= 1
    assert any(s["is_current"] for s in sessions)
