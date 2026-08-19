"""Administrative user-management operations (admin-only, enforced at the route layer)."""
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, validate_password_policy
from app.core.exceptions import AppError, email_exists, username_exists
from app.models import Role, User
from app.services import auth_audit_service as audit
from app.services import session_service, token_service


async def list_users(
    db: AsyncSession, *, search: Optional[str], role_name: Optional[str], is_active: Optional[bool],
    page: int, page_size: int,
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        like = f"%{search.strip().lower()}%"
        clause = or_(User.email.ilike(like), User.username.ilike(like), User.full_name.ilike(like))
        query = query.where(clause)
        count_query = count_query.where(clause)

    if role_name:
        role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
        role_id = role.id if role else None
        query = query.where(User.role_id == role_id)
        count_query = count_query.where(User.role_id == role_id)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    users = list((await db.execute(query)).scalars().all())
    return users, total


async def get_user(db: AsyncSession, user_id: str) -> Optional[User]:
    return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()


async def create_user(
    db: AsyncSession, *, email: str, username: str, full_name: str, password: str, role_name: str,
    actor_id: str, ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str],
) -> User:
    email = email.strip().lower()
    username = username.strip().lower()

    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise email_exists()
    if (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
        raise username_exists()

    validate_password_policy(password, email=email, username=username)
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if role is None:
        raise AppError("VALIDATION_ERROR", f"Unknown role '{role_name}'.", 422)

    user = User(
        email=email, username=username, full_name=full_name.strip(),
        hashed_password=hash_password(password), role_id=role.id,
        is_active=True, is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, attribute_names=["role"])

    await audit.log_event(
        db, action="user_created_by_admin", status="success", user_id=actor_id,
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
        metadata={"created_user_id": str(user.id), "role": role_name},
    )
    await db.commit()
    return user


async def update_user(db: AsyncSession, *, user: User, full_name: Optional[str] = None) -> User:
    if full_name is not None:
        user.full_name = full_name.strip()
    await db.commit()
    await db.refresh(user, attribute_names=["role"])
    return user


async def assign_role(
    db: AsyncSession, *, user: User, role_name: str, actor_id: str, actor_role_name: str,
    ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str],
) -> User:
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if role is None:
        raise AppError("VALIDATION_ERROR", f"Unknown role '{role_name}'.", 422)

    old_role = user.role.name if user.role else None
    if old_role == "admin" and role_name != "admin":
        # Demoting any admin (self or another) must never leave zero active administrators.
        await _guard_last_admin(db, exclude_user_id=str(user.id))

    user.role_id = role.id
    await audit.log_event(
        db, action=audit.ACTION_ROLE_CHANGED, status="success", user_id=actor_id,
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
        metadata={"target_user_id": str(user.id), "old_role": old_role, "new_role": role_name},
    )
    await db.commit()
    await db.refresh(user, attribute_names=["role"])
    return user


async def set_user_status(
    db: AsyncSession, *, user: User, is_active: bool, actor_id: str, actor_role_name: str,
    ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str],
) -> User:
    if not is_active and str(user.id) == actor_id:
        raise AppError("VALIDATION_ERROR", "You cannot disable your own account.", 400)

    if not is_active and user.role and user.role.name == "admin":
        await _guard_last_admin(db, exclude_user_id=str(user.id))

    user.is_active = is_active
    if not is_active:
        # Disabling immediately invalidates all of this user's sessions/refresh tokens.
        await token_service.revoke_all_tokens_for_user(db, str(user.id), reason="account_disabled")
        await session_service.revoke_all_sessions_for_user(db, str(user.id), reason="account_disabled")
        await audit.log_event(
            db, action=audit.ACTION_USER_DISABLED, status="success", user_id=actor_id,
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"target_user_id": str(user.id)},
        )
    else:
        await audit.log_event(
            db, action="user_activated", status="success", user_id=actor_id,
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"target_user_id": str(user.id)},
        )
    await db.commit()
    await db.refresh(user, attribute_names=["role"])
    return user


async def _guard_last_admin(db: AsyncSession, *, exclude_user_id: str) -> None:
    """Prevent removing the last remaining active admin's administrative access."""
    admin_role = (await db.execute(select(Role).where(Role.name == "admin"))).scalar_one_or_none()
    if admin_role is None:
        return
    count = (
        await db.execute(
            select(func.count()).select_from(User).where(
                User.role_id == admin_role.id, User.is_active.is_(True), User.id != exclude_user_id,
            )
        )
    ).scalar_one()
    if count == 0:
        raise AppError(
            "VALIDATION_ERROR",
            "At least one active administrator must remain. Assign another admin before changing this account.",
            400,
        )
