"""History API routes."""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import db_session
from app.models import Job, AuditLog

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def get_history(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(db_session)):
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).offset(skip).limit(limit)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "job_number": j.job_number,
            "client_name": j.client_name,
            "project_name": j.project_name,
            "status": j.status,
            "selling_price": j.selling_price,
            "currency": j.currency,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/{job_id}/audit")
async def get_audit_log(job_id: str, db: AsyncSession = Depends(db_session)):
    result = await db.execute(
        select(AuditLog).where(AuditLog.job_id == job_id)
        .order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()
    return [
        {"action": l.action, "actor": l.actor, "details": l.details_json,
         "created_at": l.created_at.isoformat()}
        for l in logs
    ]
