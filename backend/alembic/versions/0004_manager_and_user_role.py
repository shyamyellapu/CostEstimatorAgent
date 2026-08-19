"""Add `manager` role; rename the existing read-only `viewer` role to `user`.

Per product requirement: the four system roles are admin, manager, estimator, user. There is no
separate `viewer` role — the pre-existing `viewer` role (seeded in 0003) *is* the read-only
`user` role and is renamed in place so existing `viewer` accounts keep their permissions and are
never orphaned. `manager` is a new role with its own permission set. `estimator` loses
`settings.read` (not part of its permission grant in the updated matrix).

Fully idempotent — safe to run against a fresh database, a database already migrated once by
this revision, or a database where a separate `user` role was created out-of-band.

Revision ID: 0004_manager_and_user_role
Revises: 0003_auth_system
Create Date: 2026-08-05
"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0004_manager_and_user_role"
down_revision = "0003_auth_system"
branch_labels = None
depends_on = None


ALL_PERMISSION_CODES = [
    "dashboard.read",
    "estimates.create", "estimates.read", "estimates.update", "estimates.delete",
    "drawings.process", "boq.parse",
    "quotations.generate", "quotations.read",
    "excel.generate", "cover_letters.generate",
    "rfq.read", "rfq.manage",
    "job_history.read",
    "users.read", "users.create", "users.update", "users.disable", "users.assign_role",
    "sessions.read", "sessions.revoke",
    "settings.read", "settings.update",
    "audit_logs.read",
]

MANAGER_PERMISSIONS = [
    "dashboard.read", "estimates.create", "estimates.read", "estimates.update",
    "drawings.process", "boq.parse", "quotations.generate", "quotations.read",
    "excel.generate", "cover_letters.generate", "rfq.read", "rfq.manage",
    "job_history.read", "users.read", "sessions.read", "settings.read",
]

# estimator no longer includes settings.read in the updated permission matrix
ESTIMATOR_PERMISSIONS_TO_REMOVE = ["settings.read"]

USER_ROLE_DESCRIPTION = "Read-only viewer: dashboard, completed estimates, quotations, job history."
MANAGER_ROLE_DESCRIPTION = "Operational management: estimates, drawings, quotations, RFQs, read-only user/session summaries."


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # ── 1. Ensure every permission code used by the updated matrix exists (idempotent) ────────
    existing_codes = {
        row[0] for row in bind.execute(sa.text("SELECT code FROM permissions")).fetchall()
    }
    for code in ALL_PERMISSION_CODES:
        if code not in existing_codes:
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, name, resource, action, created_at) "
                    "VALUES (:id, :code, :name, :resource, :action, :created_at)"
                ),
                {
                    "id": uuid.uuid4(), "code": code, "name": code.replace(".", " ").title(),
                    "resource": code.split(".")[0], "action": code.split(".")[-1], "created_at": now,
                },
            )

    # ── 2. Resolve the `user` role: rename `viewer` in place, or merge if both already exist ──
    viewer_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'viewer'")).fetchone()
    user_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'user'")).fetchone()

    if viewer_row and not user_row:
        # Simple, safe rename — preserves the role id, its users, and its role_permissions rows.
        bind.execute(
            sa.text("UPDATE roles SET name = 'user', description = :desc WHERE id = :id"),
            {"desc": USER_ROLE_DESCRIPTION, "id": viewer_row[0]},
        )
        user_role_id = viewer_row[0]
    elif viewer_row and user_row:
        # Both exist (out-of-band data): merge viewer into user, never orphaning users/permissions.
        user_role_id = user_row[0]
        viewer_role_id = viewer_row[0]
        bind.execute(
            sa.text("UPDATE users SET role_id = :user_id WHERE role_id = :viewer_id"),
            {"user_id": user_role_id, "viewer_id": viewer_role_id},
        )
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT :user_id, permission_id FROM role_permissions WHERE role_id = :viewer_id "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {"user_id": user_role_id, "viewer_id": viewer_role_id},
        )
        bind.execute(sa.text("DELETE FROM role_permissions WHERE role_id = :id"), {"id": viewer_role_id})
        bind.execute(sa.text("DELETE FROM roles WHERE id = :id"), {"id": viewer_role_id})
    elif user_row:
        user_role_id = user_row[0]
    else:
        user_role_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO roles (id, name, description, is_system_role, created_at) "
                "VALUES (:id, 'user', :desc, true, :created_at)"
            ),
            {"id": user_role_id, "desc": USER_ROLE_DESCRIPTION, "created_at": now},
        )

    # ── 3. Ensure `manager` role exists ────────────────────────────────────────────────────────
    manager_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'manager'")).fetchone()
    if manager_row:
        manager_role_id = manager_row[0]
    else:
        manager_role_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO roles (id, name, description, is_system_role, created_at) "
                "VALUES (:id, 'manager', :desc, true, :created_at)"
            ),
            {"id": manager_role_id, "desc": MANAGER_ROLE_DESCRIPTION, "created_at": now},
        )

    # ── 4. Grant manager its permission set (idempotent) ──────────────────────────────────────
    permission_ids = dict(
        bind.execute(sa.text("SELECT code, id FROM permissions")).fetchall()
    )
    for code in MANAGER_PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {"role_id": manager_role_id, "perm_id": permission_ids[code]},
        )

    # ── 5. Trim estimator's permission set to the updated matrix ─────────────────────────────
    estimator_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'estimator'")).fetchone()
    if estimator_row:
        for code in ESTIMATOR_PERMISSIONS_TO_REMOVE:
            bind.execute(
                sa.text(
                    "DELETE FROM role_permissions WHERE role_id = :role_id AND permission_id = :perm_id"
                ),
                {"role_id": estimator_row[0], "perm_id": permission_ids[code]},
            )


def downgrade() -> None:
    bind = op.get_bind()

    manager_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'manager'")).fetchone()
    if manager_row:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE role_id = :id"), {"id": manager_row[0]})
        # Users on the manager role are reassigned to `user` rather than left orphaned.
        user_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'user'")).fetchone()
        if user_row:
            bind.execute(
                sa.text("UPDATE users SET role_id = :user_id WHERE role_id = :manager_id"),
                {"user_id": user_row[0], "manager_id": manager_row[0]},
            )
        bind.execute(sa.text("DELETE FROM roles WHERE id = :id"), {"id": manager_row[0]})

    user_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'user'")).fetchone()
    if user_row:
        bind.execute(
            sa.text("UPDATE roles SET name = 'viewer', description = :desc WHERE id = :id"),
            {"desc": "Read-only access to completed work", "id": user_row[0]},
        )

    estimator_row = bind.execute(sa.text("SELECT id FROM roles WHERE name = 'estimator'")).fetchone()
    settings_read_row = bind.execute(sa.text("SELECT id FROM permissions WHERE code = 'settings.read'")).fetchone()
    if estimator_row and settings_read_row:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id) "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {"role_id": estimator_row[0], "perm_id": settings_read_row[0]},
        )
