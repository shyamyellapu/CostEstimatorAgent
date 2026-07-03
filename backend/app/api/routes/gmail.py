"""
Gmail API routes — OAuth2 flow, mailbox management, inbox, sync.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.models import GmailCredential, RFQEmail, RFQAttachment
from app.services.gmail_service import (
    get_authorization_url,
    exchange_code_for_credentials,
    get_authenticated_email,
    GmailSyncService,
)
from app.tasks.rfq_tasks import enqueue

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class OAuthCallbackBody(BaseModel):
    code: str
    redirect_uri: str
    state: Optional[str] = None


class SyncRequest(BaseModel):
    mailbox_id: Optional[str] = None
    max_messages: int = 20


# ─── Auth flow ────────────────────────────────────────────────────────────────

@router.get("/auth-url")
async def get_auth_url(
    redirect_uri: str = Query(..., description="OAuth2 callback URL"),
    state: Optional[str] = None,
):
    """Return the Gmail OAuth2 consent URL."""
    logger.info("gmail_auth_url_requested redirect_uri=%s state_present=%s", redirect_uri, bool(state))
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        logger.error("gmail_auth_url_failed reason=oauth_not_configured")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Gmail OAuth2 not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET.",
        )
    try:
        auth_url, returned_state = get_authorization_url(redirect_uri, state)
    except Exception as exc:
        logger.exception("gmail_auth_url_failed redirect_uri=%s", redirect_uri)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to build OAuth URL: {exc}")
    return {"auth_url": auth_url, "state": returned_state}


@router.post("/callback")
async def oauth_callback(body: OAuthCallbackBody, db: AsyncSession = Depends(get_db)):
    """
    Exchange authorization code for tokens, store credential, return mailbox info.
    """
    logger.info("gmail_oauth_callback_started redirect_uri=%s state_present=%s", body.redirect_uri, bool(body.state))
    try:
        creds_dict = exchange_code_for_credentials(body.code, body.redirect_uri)
        email_address = get_authenticated_email(creds_dict)
    except Exception as exc:
        logger.exception("gmail_oauth_callback_failed redirect_uri=%s", body.redirect_uri)
        raise HTTPException(400, f"OAuth2 exchange failed: {exc}")

    svc = GmailSyncService(db)
    cred = await svc.upsert_credential(
        email_address=email_address,
        creds_dict=creds_dict,
        display_name=email_address,
    )
    await db.commit()
    logger.info("gmail_oauth_callback_completed mailbox_id=%s email=%s", cred.id, cred.email_address)
    return {
        "mailbox_id": cred.id,
        "email_address": cred.email_address,
        "is_active": cred.is_active,
    }


# ─── Mailbox management ───────────────────────────────────────────────────────

@router.get("/mailboxes")
async def list_mailboxes(db: AsyncSession = Depends(get_db)):
    logger.info("gmail_mailboxes_list_requested")
    result = await db.execute(select(GmailCredential).order_by(GmailCredential.created_at))
    mailboxes = result.scalars().all()
    return [
        {
            "id": m.id,
            "email_address": m.email_address,
            "display_name": m.display_name,
            "is_active": m.is_active,
            "last_synced": m.last_synced.isoformat() if m.last_synced else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in mailboxes
    ]


@router.delete("/mailboxes/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_mailbox(mailbox_id: str, db: AsyncSession = Depends(get_db)):
    logger.info("gmail_mailbox_disconnect_requested mailbox_id=%s", mailbox_id)
    res = await db.execute(
        select(GmailCredential).where(GmailCredential.id == mailbox_id)
    )
    cred = res.scalar_one_or_none()
    if not cred:
        raise HTTPException(404, "Mailbox not found")
    cred.is_active = False
    cred.credentials_json = None   # revoke stored token
    await db.commit()
    logger.info("gmail_mailbox_disconnected mailbox_id=%s email=%s", mailbox_id, cred.email_address)


@router.post("/mailboxes/{mailbox_id}/reconnect")
async def reconnect_mailbox(mailbox_id: str, db: AsyncSession = Depends(get_db)):
    """Re-enable a disconnected mailbox (credentials must still be valid)."""
    logger.info("gmail_mailbox_reconnect_requested mailbox_id=%s", mailbox_id)
    res = await db.execute(
        select(GmailCredential).where(GmailCredential.id == mailbox_id)
    )
    cred = res.scalar_one_or_none()
    if not cred:
        raise HTTPException(404, "Mailbox not found")
    if not cred.credentials_json:
        raise HTTPException(400, "No credentials stored. Re-authenticate via /auth-url.")
    cred.is_active = True
    await db.commit()
    logger.info("gmail_mailbox_reconnected mailbox_id=%s email=%s", mailbox_id, cred.email_address)
    return {"status": "reconnected", "email_address": cred.email_address}


# ─── Sync ─────────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_gmail(body: SyncRequest, db: AsyncSession = Depends(get_db)):
    """
    Sync one or all mailboxes.
    For each new RFQ-type email found, enqueue a process_email task.
    """
    logger.info(
        "gmail_sync_requested mailbox_id=%s max_messages=%d",
        body.mailbox_id or "all",
        body.max_messages,
    )
    svc = GmailSyncService(db)

    if body.mailbox_id:
        mailbox = await svc.get_mailbox(body.mailbox_id)
        if not mailbox:
            logger.warning("gmail_sync_mailbox_not_found mailbox_id=%s", body.mailbox_id)
            raise HTTPException(404, "Mailbox not found")
        counters = await svc.sync_mailbox(mailbox, max_messages=body.max_messages)
        if counters.get("needs_reauth"):
            mailbox.credentials_json = None  # wipe stale token — force fresh OAuth
        mailboxes_synced = 1
    else:
        all_mb = await svc.get_active_mailboxes()
        counters: Dict[str, Any] = {"fetched": 0, "new_rfq": 0, "skipped": 0, "errors": 0, "available": 0, "needs_reauth": False}
        for mb in all_mb:
            c = await svc.sync_mailbox(mb, max_messages=body.max_messages)
            for k in ("fetched", "new_rfq", "skipped", "errors", "available"):
                counters[k] = counters.get(k, 0) + c.get(k, 0)
            if c.get("needs_reauth"):
                counters["needs_reauth"] = True
                mb.credentials_json = None  # wipe stale token — force fresh OAuth
        mailboxes_synced = len(all_mb)

    # Enqueue process_email tasks for unprocessed RFQ emails
    email_res = await db.execute(
        select(RFQEmail).where(
            RFQEmail.is_processed == False,
            RFQEmail.email_type.in_(["rfq", "revision"]),
        ).limit(100)
    )
    emails = email_res.scalars().all()
    for email in emails:
        await enqueue(db, "process_email", "email", email.id, priority=2)

    await db.commit()
    logger.info(
        "gmail_sync_completed mailbox_id=%s mailboxes_synced=%d counters=%s process_tasks_queued=%d",
        body.mailbox_id or "all",
        mailboxes_synced,
        counters,
        len(emails),
    )

    return {
        "mailboxes_synced": mailboxes_synced,
        "counters": counters,
        "process_tasks_queued": len(emails),
    }


# ─── Inbox ────────────────────────────────────────────────────────────────────

@router.get("/inbox")
async def get_inbox(
    email_type: Optional[str] = None,
    is_processed: Optional[bool] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of fetched emails."""
    logger.info(
        "gmail_inbox_requested email_type=%s is_processed=%s limit=%d offset=%d",
        email_type,
        is_processed,
        limit,
        offset,
    )
    q = select(RFQEmail).order_by(RFQEmail.received_at.desc())
    if email_type:
        q = q.where(RFQEmail.email_type == email_type)
    if is_processed is not None:
        q = q.where(RFQEmail.is_processed == is_processed)
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    emails = result.scalars().all()

    return [
        {
            "id": e.id,
            "gmail_message_id": e.gmail_message_id,
            "mailbox_email": e.mailbox_email,
            "subject": e.subject,
            "sender_email": e.sender_email,
            "sender_name": e.sender_name,
            "received_at": e.received_at.isoformat() if e.received_at else None,
            "email_type": e.email_type,
            "rfq_id": e.rfq_id,
            "is_processed": e.is_processed,
            "attachment_count": len(e.attachments),
        }
        for e in emails
    ]


@router.get("/inbox/{email_id}")
async def get_email_detail(email_id: str, db: AsyncSession = Depends(get_db)):
    logger.info("gmail_email_detail_requested email_id=%s", email_id)
    res = await db.execute(select(RFQEmail).where(RFQEmail.id == email_id))
    email = res.scalar_one_or_none()
    if not email:
        raise HTTPException(404, "Email not found")
    return {
        "id": email.id,
        "gmail_message_id": email.gmail_message_id,
        "gmail_thread_id": email.gmail_thread_id,
        "mailbox_email": email.mailbox_email,
        "subject": email.subject,
        "sender_email": email.sender_email,
        "sender_name": email.sender_name,
        "recipients": email.recipients,
        "body_text": email.body_text,
        "received_at": email.received_at.isoformat() if email.received_at else None,
        "email_type": email.email_type,
        "rfq_id": email.rfq_id,
        "is_processed": email.is_processed,
        "labels": email.labels,
        "attachments": [
            {
                "id": a.id,
                "filename": a.original_filename,
                "mime_type": a.mime_type,
                "file_size": a.file_size,
                "file_category": a.file_category,
                "document_type": a.document_type,
            }
            for a in email.attachments
        ],
    }


@router.post("/inbox/{email_id}/process")
async def process_email_manually(email_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger RFQ creation from an email."""
    logger.info("gmail_email_process_requested email_id=%s", email_id)
    res = await db.execute(select(RFQEmail).where(RFQEmail.id == email_id))
    email = res.scalar_one_or_none()
    if not email:
        raise HTTPException(404, "Email not found")

    task = await enqueue(db, "process_email", "email", email.id, priority=1)
    await db.commit()
    logger.info("gmail_email_process_queued email_id=%s task_id=%s", email_id, task.id)
    return {"task_id": task.id, "status": "queued"}
