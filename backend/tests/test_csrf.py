from tests.helpers import auth_headers, register_and_login


def test_csrf_failure_on_logout_without_token(client):
    _, _, access_token = register_and_login(client)
    # Deliberately omit the X-CSRF-Token header — cookie-authenticated state-changing endpoints
    # must reject this even though the Authorization bearer token itself is valid.
    resp = client.post("/api/auth/logout", headers=auth_headers(access_token))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_CSRF_INVALID"


def test_csrf_failure_with_mismatched_header(client):
    _, _, access_token = register_and_login(client)
    resp = client.post(
        "/api/auth/logout",
        headers={**auth_headers(access_token), "X-CSRF-Token": "does-not-match-the-cookie"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_CSRF_INVALID"
