"""Admin-only audit-log viewing endpoint."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.database import get_db
from app.models import AuthAuditLog
from app.schemas.audit import AuditLogListResponse, AuthAuditLogOut

router = APIRouter()


@router.get("/audit-logs", response_model=AuditLogListResponse, dependencies=[Depends(require_permission("audit_logs.read"))])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query = select(AuthAuditLog)
    count_query = select(func.count()).select_from(AuthAuditLog)

    if user_id:
        query, count_query = query.where(AuthAuditLog.user_id == user_id), count_query.where(AuthAuditLog.user_id == user_id)
    if action:
        query, count_query = query.where(AuthAuditLog.action == action), count_query.where(AuthAuditLog.action == action)
    if since:
        query, count_query = query.where(AuthAuditLog.timestamp >= since), count_query.where(AuthAuditLog.timestamp >= since)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(AuthAuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return AuditLogListResponse(
        items=[
            AuthAuditLogOut(
                id=str(r.id), user_id=str(r.user_id) if r.user_id else None, action=r.action, status=r.status,
                ip_address=r.ip_address, request_id=r.request_id, timestamp=r.timestamp, metadata_json=r.metadata_json,
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )
