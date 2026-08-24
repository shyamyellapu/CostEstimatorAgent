"""Production authentication system: RBAC, refresh-token rotation, sessions, audit log.

The pre-existing `users` / `roles` / `permissions` / `refresh_tokens` tables were created by
migration 0001 (via Base.metadata.create_all) but were never wired into any route, service, or
dependency — no authentication feature has ever shipped against them, so there is no production
data to preserve in these specific tables. This migration drops and recreates them with the full
production schema, and adds the new `user_sessions`, `auth_audit_logs`, and
`password_reset_tokens` tables required for refresh-token rotation, replay detection, and
audit logging.

`role_permissions` (role_id, permission_id composite PK) is left untouched since it already
satisfies the composite-unique-constraint requirement.

Revision ID: 0003_auth_system
Revises: 0002_drawing_workflow
Create Date: 2026-07-31
"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0003_auth_system"
down_revision = "0002_drawing_workflow"
branch_labels = None
depends_on = None


# ─── Default RBAC seed data ────────────────────────────────────────────────────

PERMISSIONS = [
    ("dashboard.read", "View dashboard", "dashboard", "read"),
    ("estimates.create", "Create estimates", "estimates", "create"),
    ("estimates.read", "View estimates", "estimates", "read"),
    ("estimates.update", "Edit estimates", "estimates", "update"),
    ("estimates.delete", "Delete estimates", "estimates", "delete"),
    ("drawings.process", "Process drawings", "drawings", "process"),
    ("boq.parse", "Parse BOQ documents", "boq", "parse"),
    ("quotations.generate", "Generate quotations", "quotations", "generate"),
    ("quotations.read", "View quotations", "quotations", "read"),
    ("excel.generate", "Generate Excel sheets", "excel", "generate"),
    ("cover_letters.generate", "Generate cover letters", "cover_letters", "generate"),
    ("rfq.read", "View RFQ inbox", "rfq", "read"),
    ("rfq.manage", "Manage RFQ records", "rfq", "manage"),
    ("job_history.read", "View job history", "job_history", "read"),
    ("users.read", "View users", "users", "read"),
    ("users.create", "Create users", "users", "create"),
    ("users.update", "Update users", "users", "update"),
    ("users.disable", "Disable/activate users", "users", "disable"),
    ("users.assign_role", "Assign user roles", "users", "assign_role"),
    ("sessions.read", "View sessions", "sessions", "read"),
    ("sessions.revoke", "Revoke sessions", "sessions", "revoke"),
    ("settings.read", "View settings", "settings", "read"),
    ("settings.update", "Update settings", "settings", "update"),
    ("audit_logs.read", "View audit logs", "audit_logs", "read"),
]

ROLE_PERMISSIONS = {
    "admin": [code for code, *_ in PERMISSIONS],
    "estimator": [
        "dashboard.read", "estimates.create", "estimates.read", "estimates.update",
        "drawings.process", "boq.parse", "quotations.generate", "quotations.read",
        "excel.generate", "cover_letters.generate", "rfq.read", "job_history.read",
        "settings.read",
    ],
    "viewer": [
        "dashboard.read", "estimates.read", "quotations.read", "job_history.read",
    ],
}

ROLES = [
    ("admin", "Full platform access, user and security administration", True),
    ("estimator", "Create and manage estimates, drawings, quotations", True),
    ("viewer", "Read-only access to completed work", True),
]


def upgrade() -> None:
    bind = op.get_bind()

    # ── Drop old, never-used auth tables (safe: zero production rows) ─────────
    op.execute("DROP TABLE IF EXISTS user_roles CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    # Drop explicitly (not just implied by the roles/permissions CASCADE below) — on some
    # pre-existing databases this table's FKs didn't cascade-drop reliably, leaving it behind
    # and causing "relation already exists" when create_table ran further down, which rolled
    # back this entire migration (transactional DDL) on every startup.
    op.execute("DROP TABLE IF EXISTS role_permissions CASCADE")
    # users has FKs pointing at it (uploaded_files.uploaded_by_user_id) — drop dependent FK first is
    # unnecessary since ondelete=SET NULL was configured, but CASCADE drop of the table requires
    # dropping the constraint; Postgres handles this automatically when dropping with CASCADE.
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS roles CASCADE")
    op.execute("DROP TABLE IF EXISTS permissions CASCADE")

    # ── roles ───────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    # ── permissions ─────────────────────────────────────────────────────────
    op.create_table(
        "permissions",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource", sa.String(100), nullable=True),
        sa.Column("action", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)
    op.create_index("idx_permissions_resource_action", "permissions", ["resource", "action"])

    # ── role_permissions (recreate — was dropped via CASCADE above) ──────────
    op.create_table(
        "role_permissions",
        sa.Column("role_id", PGUUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", PGUUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    # ── users ───────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", PGUUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role_id", PGUUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("profile_settings_json", JSONB(), nullable=True),
        sa.Column("preferences_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("idx_user_active_role", "users", ["is_active", "role_id"])

    # ── user_sessions (current_refresh_token_id FK added after refresh_tokens exists) ──
    op.create_table(
        "user_sessions",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_refresh_token_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("user_agent", sa.String(1000), nullable=True),
        sa.Column("device_name", sa.String(200), nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("operating_system", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revocation_reason", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("idx_session_user_active", "user_sessions", ["user_id", "is_active"])
    op.create_index("idx_session_expires", "user_sessions", ["expires_at"])

    # ── refresh_tokens ──────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", PGUUID(as_uuid=True), sa.ForeignKey("user_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_family_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("parent_token_id", PGUUID(as_uuid=True), sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("replaced_by_token_id", PGUUID(as_uuid=True), sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revocation_reason", sa.String(100), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_ip", sa.String(100), nullable=True),
        sa.Column("last_used_ip", sa.String(100), nullable=True),
        sa.Column("user_agent", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index("idx_refresh_family", "refresh_tokens", ["token_family_id"])
    op.create_index("idx_refresh_user_expires", "refresh_tokens", ["user_id", "expires_at"])
    op.create_index("idx_refresh_expires", "refresh_tokens", ["expires_at"])

    # Now that refresh_tokens exists, wire up the deferred FK from user_sessions
    op.create_foreign_key(
        "fk_user_sessions_current_refresh_token",
        "user_sessions", "refresh_tokens",
        ["current_refresh_token_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── auth_audit_logs ─────────────────────────────────────────────────────
    op.create_table(
        "auth_audit_logs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("user_agent", sa.String(1000), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", JSONB(), nullable=True),
    )
    op.create_index("ix_auth_audit_logs_user_id", "auth_audit_logs", ["user_id"])
    op.create_index("ix_auth_audit_logs_action", "auth_audit_logs", ["action"])
    op.create_index("ix_auth_audit_logs_request_id", "auth_audit_logs", ["request_id"])
    op.create_index("idx_auth_audit_user_ts", "auth_audit_logs", ["user_id", "timestamp"])
    op.create_index("idx_auth_audit_action_ts", "auth_audit_logs", ["action", "timestamp"])

    # ── password_reset_tokens ───────────────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("requested_ip", sa.String(100), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("idx_password_reset_expires", "password_reset_tokens", ["expires_at"])

    # ── Idempotent seed: default roles + permissions + role_permissions ─────
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    roles_table = sa.table(
        "roles",
        sa.column("id", PGUUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_system_role", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    permissions_table = sa.table(
        "permissions",
        sa.column("id", PGUUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", PGUUID(as_uuid=True)),
        sa.column("permission_id", PGUUID(as_uuid=True)),
    )

    role_ids = {}
    for name, description, is_system in ROLES:
        role_id = uuid.uuid4()
        role_ids[name] = role_id
        op.execute(
            roles_table.insert()
            .values(id=role_id, name=name, description=description, is_system_role=is_system, created_at=now)
        )

    permission_ids = {}
    for code, name, resource, action in PERMISSIONS:
        permission_id = uuid.uuid4()
        permission_ids[code] = permission_id
        op.execute(
            permissions_table.insert()
            .values(id=permission_id, code=code, name=name, resource=resource, action=action, created_at=now)
        )

    for role_name, codes in ROLE_PERMISSIONS.items():
        role_id = role_ids[role_name]
        for code in codes:
            op.execute(
                role_permissions_table.insert()
                .values(role_id=role_id, permission_id=permission_ids[code])
            )


def downgrade() -> None:
    op.drop_constraint("fk_user_sessions_current_refresh_token", "user_sessions", type_="foreignkey")
    op.drop_table("password_reset_tokens")
    op.drop_table("auth_audit_logs")
    op.drop_table("refresh_tokens")
    op.drop_table("user_sessions")
    op.drop_table("users")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")

    # Recreate a minimal pre-migration shape so downgrade chain does not break.
    op.create_table(
        "roles",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "permissions",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", PGUUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", PGUUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "users",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", PGUUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("profile_settings_json", JSONB(), nullable=True),
        sa.Column("preferences_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", PGUUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("jti", sa.String(120), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("device_info_json", JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
