from tests.conftest import create_user
from tests.helpers import auth_headers, csrf_headers, login, unique


def _login_as(client, role_name: str):
    email = f"{unique(role_name)}@example.com"
    username = unique(f"{role_name}user")
    create_user(email, username, "Str0ng!Passw0rd", role_name)
    resp = login(client, email)
    return resp.json()["access_token"]


def test_rbac_admin_can_access_admin_users_endpoint(client):
    token = _login_as(client, "admin")
    resp = client.get("/api/admin/users", headers=auth_headers(token))
    assert resp.status_code == 200


def test_rbac_estimator_denied_admin_users_endpoint(client):
    token = _login_as(client, "estimator")
    resp = client.get("/api/admin/users", headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_PERMISSION_DENIED"


def test_rbac_user_denied_admin_users_endpoint(client):
    token = _login_as(client, "user")
    resp = client.get("/api/admin/users", headers=auth_headers(token))
    assert resp.status_code == 403


def test_rbac_user_cannot_read_or_update_settings(client):
    """Per the RBAC matrix, settings.read is granted to admin/manager only — the read-only
    `user` role gets neither read nor update."""
    token = _login_as(client, "user")
    read_resp = client.get("/api/settings", headers=auth_headers(token))
    assert read_resp.status_code == 403

    write_resp = client.put(
        "/api/settings", headers={**auth_headers(token), **csrf_headers(client)},
        json=[{"key": "test_rate", "value": 1.0}],
    )
    assert write_resp.status_code == 403


def test_permission_dependency_estimator_cannot_read_or_update_settings(client):
    """estimator has no settings.* permission in the updated RBAC matrix."""
    token = _login_as(client, "estimator")
    read_resp = client.get("/api/settings", headers=auth_headers(token))
    assert read_resp.status_code == 403
    write_resp = client.put(
        "/api/settings", headers={**auth_headers(token), **csrf_headers(client)},
        json=[{"key": "test_rate", "value": 2.0}],
    )
    assert write_resp.status_code == 403


def test_rbac_manager_can_read_but_not_update_settings(client):
    """manager has settings.read but not settings.update."""
    token = _login_as(client, "manager")
    read_resp = client.get("/api/settings", headers=auth_headers(token))
    assert read_resp.status_code == 200
    write_resp = client.put(
        "/api/settings", headers={**auth_headers(token), **csrf_headers(client)},
        json=[{"key": "test_rate", "value": 3.0}],
    )
    assert write_resp.status_code == 403


def test_rbac_manager_cannot_assign_roles_or_disable_users(client):
    manager_token = _login_as(client, "manager")
    target_email = f"{unique('mgrtarget')}@example.com"
    target_id = create_user(target_email, unique("mgrtargetuser"), "Str0ng!Passw0rd", "user")

    assign_resp = client.patch(
        f"/api/admin/users/{target_id}/role",
        headers={**auth_headers(manager_token), **csrf_headers(client)}, json={"role": "admin"},
    )
    assert assign_resp.status_code == 403

    status_resp = client.patch(
        f"/api/admin/users/{target_id}/status",
        headers={**auth_headers(manager_token), **csrf_headers(client)}, json={"is_active": False},
    )
    assert status_resp.status_code == 403


def test_rbac_manager_cannot_read_audit_logs(client):
    token = _login_as(client, "manager")
    resp = client.get("/api/admin/audit-logs", headers=auth_headers(token))
    assert resp.status_code == 403


def test_admin_can_revoke_another_users_session(client):
    admin_token = _login_as(client, "admin")

    target_email = f"{unique('target')}@example.com"
    create_user(target_email, unique("targetuser"), "Str0ng!Passw0rd", "user")
    target_login = login(client, target_email)
    target_access = target_login.json()["access_token"]

    admin_sessions = client.get("/api/admin/sessions", headers=auth_headers(admin_token))
    assert admin_sessions.status_code == 200
    target_session = next(s for s in admin_sessions.json() if s["user_email"] == target_email)

    revoke = client.delete(
        f"/api/admin/sessions/{target_session['id']}",
        headers={**auth_headers(admin_token), **csrf_headers(client)},
    )
    assert revoke.status_code == 204

    # The target user's access token must now be rejected — the session was revoked.
    me_resp = client.get("/api/auth/me", headers=auth_headers(target_access))
    assert me_resp.status_code == 401
