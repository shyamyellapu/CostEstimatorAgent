"""
Gmail OAuth2 integration service.

Handles:
- OAuth2 authorization flow (web-based consent)
- Token storage / refresh via GmailCredential model
- Fetching messages, threads, and attachments
- RFQ email detection heuristics
- Incremental mailbox sync using Gmail historyId
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import GmailCredential, RFQEmail, RFQAttachment
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RFQ detection keyword sets
# ---------------------------------------------------------------------------
RFQ_SUBJECT_KEYWORDS = [
    "rfq", "request for quotation", "request for quote", "enquiry", "inquiry",
    "tender", "itb", "invitation to bid", "rfp", "request for proposal",
    "quotation request", "price request", "cost inquiry", "bom", "bill of material",
    "supply of", "fabrication of", "manufacture of", "procurement",
]
REVISION_KEYWORDS = ["revision", "rev.", "revised", "amendment", "updated rfq", "revision to"]
CLARIFICATION_KEYWORDS = ["clarification", "query", "question", "follow up", "follow-up", "response to"]


# ---------------------------------------------------------------------------
# OAuth2 helpers (google-auth library)
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_AUTH_URI  = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_authorization_url(redirect_uri: str, state: Optional[str] = None) -> Tuple[str, str]:
    """
    Return (authorization_url, state) for the Google OAuth2 consent screen.

    We use requests_oauthlib.OAuth2Session directly instead of the
    google-auth-oauthlib Flow class.  The Flow class (v1.4+) automatically
    injects PKCE (code_challenge / code_verifier).  Since the verifier lives
    inside the Flow object, creating a new Flow on the callback loses it and
    Google rejects the token exchange.  OAuth2Session does NOT add PKCE unless
    you explicitly pass code_verifier, so the authorization ↔ exchange pair
    stays stateless and reliable.
    """
    try:
        from requests_oauthlib import OAuth2Session  # type: ignore
    except ImportError:
        raise RuntimeError("requests-oauthlib is not installed. Run: pip install requests-oauthlib")

    import secrets
    generated_state = state or secrets.token_urlsafe(22)
    session = OAuth2Session(
        client_id=settings.gmail_client_id,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        state=generated_state,
    )
    auth_url, returned_state = session.authorization_url(
        _AUTH_URI,
        access_type="offline",
        prompt="consent",
    )
    return auth_url, returned_state


def exchange_code_for_credentials(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Exchange authorization code for a token dict (no PKCE required)."""
    try:
        from requests_oauthlib import OAuth2Session  # type: ignore
    except ImportError:
        raise RuntimeError("requests-oauthlib is not installed.")

    import os
    # requests-oauthlib by default enforces HTTPS; allow HTTP for localhost dev
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    session = OAuth2Session(
        client_id=settings.gmail_client_id,
        redirect_uri=redirect_uri,
    )
    token = session.fetch_token(
        _TOKEN_URI,
        code=code,
        client_secret=settings.gmail_client_secret,
    )
    return {
        "token": token.get("access_token"),
        "refresh_token": token.get("refresh_token"),
        "token_uri": _TOKEN_URI,
        "client_id": settings.gmail_client_id,
        "client_secret": settings.gmail_client_secret,
        "scopes": SCOPES,
        "expiry": None,
    }


def _credentials_to_dict(creds) -> Dict[str, Any]:
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def _build_credentials(creds_dict: Dict[str, Any]):
    """Rebuild google.oauth2.credentials.Credentials from stored dict."""
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except ImportError:
        raise RuntimeError("google-auth is not installed.")

    import os
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    # Fall back to live settings if the stored dict has empty client credentials
    client_id = creds_dict.get("client_id") or settings.gmail_client_id
    client_secret = creds_dict.get("client_secret") or settings.gmail_client_secret

    expiry = None
    if creds_dict.get("expiry"):
        try:
            expiry = datetime.fromisoformat(creds_dict["expiry"]).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    creds = Credentials(
        token=creds_dict.get("token"),
        refresh_token=creds_dict.get("refresh_token"),
        token_uri=creds_dict.get("token_uri", _TOKEN_URI),
        client_id=client_id,
        client_secret=client_secret,
        scopes=creds_dict.get("scopes", SCOPES),
        expiry=expiry,
    )
    # Always refresh: expiry is stored as None so we can't trust creds.expired.
    # A fresh access_token also picks up the current scopes on the refresh_token.
    if creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            logger.warning("Token refresh failed: %s", exc)
            raise
    return creds


def _build_gmail_service(creds_dict: Dict[str, Any]):
    """Return an authenticated Gmail API service object."""
    try:
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        raise RuntimeError("google-api-python-client is not installed.")
    creds = _build_credentials(creds_dict)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_authenticated_email(creds_dict: Dict[str, Any]) -> str:
    """Fetch the email address of the authenticated user."""
    service = _build_gmail_service(creds_dict)
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "")


# ---------------------------------------------------------------------------
# Message fetching
# ---------------------------------------------------------------------------

def _decode_body(part: Dict) -> str:
    """Decode a base64url encoded Gmail message part body."""
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_parts(parts: List[Dict], mime_type: str) -> str:
    """Recursively extract text from message parts matching mime_type."""
    result = ""
    for part in parts:
        if part.get("mimeType") == mime_type:
            result += _decode_body(part)
        if "parts" in part:
            result += _extract_parts(part["parts"], mime_type)
    return result


def _parse_message(raw: Dict) -> Dict[str, Any]:
    """Parse a raw Gmail API message into a flat dict."""
    headers = {h["name"].lower(): h["value"] for h in raw.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "")
    from_header = headers.get("from", "")
    to_header = headers.get("to", "")
    date_str = headers.get("date", "")

    # Parse sender
    sender_match = re.match(r"^(.*?)<([^>]+)>$", from_header.strip())
    if sender_match:
        sender_name = sender_match.group(1).strip().strip('"')
        sender_email = sender_match.group(2).strip()
    else:
        sender_name = ""
        sender_email = from_header.strip()

    # Parse date
    received_at = None
    if date_str:
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            pass

    # Body extraction
    payload = raw.get("payload", {})
    body_text = ""
    body_html = ""
    if payload.get("mimeType") == "text/plain":
        body_text = _decode_body(payload)
    elif payload.get("mimeType") == "text/html":
        body_html = _decode_body(payload)
    else:
        parts = payload.get("parts", [])
        body_text = _extract_parts(parts, "text/plain")
        body_html = _extract_parts(parts, "text/html")

    # Attachments
    attachments = []
    def _collect_attachments(parts_list):
        for part in parts_list:
            if part.get("filename"):
                attachments.append({
                    "gmail_attachment_id": part.get("body", {}).get("attachmentId"),
                    "filename": part["filename"],
                    "mime_type": part.get("mimeType", ""),
                    "file_size": part.get("body", {}).get("size", 0),
                })
            if "parts" in part:
                _collect_attachments(part["parts"])

    _collect_attachments(payload.get("parts", []))

    return {
        "gmail_message_id": raw["id"],
        "gmail_thread_id": raw.get("threadId", ""),
        "subject": subject,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "recipients": [r.strip() for r in to_header.split(",") if r.strip()],
        "body_text": body_text[:50000],   # safety cap
        "body_html": body_html[:100000],
        "received_at": received_at,
        "labels": raw.get("labelIds", []),
        "attachments": attachments,
    }


# ---------------------------------------------------------------------------
# RFQ classification heuristics
# ---------------------------------------------------------------------------

def classify_email_type(subject: str, body: str) -> str:
    """Classify email as rfq / revision / clarification / other."""
    text = (subject + " " + body[:2000]).lower()
    if any(kw in text for kw in REVISION_KEYWORDS):
        return "revision"
    if any(kw in text for kw in CLARIFICATION_KEYWORDS):
        return "clarification"
    if any(kw in text for kw in RFQ_SUBJECT_KEYWORDS):
        return "rfq"
    return "other"


def is_rfq_email(subject: str, body: str, has_attachments: bool) -> bool:
    """Heuristic: is this email likely an RFQ?"""
    etype = classify_email_type(subject, body)
    return etype in ("rfq", "revision")


# ---------------------------------------------------------------------------
# Database-backed sync
# ---------------------------------------------------------------------------

class GmailSyncService:
    """Handles syncing Gmail mailboxes with the database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_mailboxes(self) -> List[GmailCredential]:
        result = await self.db.execute(
            select(GmailCredential).where(GmailCredential.is_active == True)
        )
        return list(result.scalars().all())

    async def get_mailbox(self, mailbox_id: str) -> Optional[GmailCredential]:
        result = await self.db.execute(
            select(GmailCredential).where(GmailCredential.id == mailbox_id)
        )
        return result.scalar_one_or_none()

    async def upsert_credential(
        self,
        email_address: str,
        creds_dict: Dict[str, Any],
        display_name: Optional[str] = None,
    ) -> GmailCredential:
        result = await self.db.execute(
            select(GmailCredential).where(GmailCredential.email_address == email_address)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.credentials_json = creds_dict
            existing.is_active = True
            if display_name:
                existing.display_name = display_name
            await self.db.flush()
            return existing
        cred = GmailCredential(
            email_address=email_address,
            display_name=display_name or email_address,
            credentials_json=creds_dict,
            is_active=True,
        )
        self.db.add(cred)
        await self.db.flush()
        return cred

    async def sync_mailbox(
        self,
        mailbox: GmailCredential,
        max_messages: int = 50,
    ) -> Dict[str, Any]:
        """
        Fetch new/updated messages from Gmail and persist them.
        Returns counters: {fetched, new_rfq, skipped, errors, available, needs_reauth}.
        """
        import asyncio

        if not mailbox.credentials_json:
            return {"error": "no credentials", "fetched": 0, "new_rfq": 0, "skipped": 0,
                    "errors": 0, "available": 0, "needs_reauth": True}

        try:
            loop = asyncio.get_event_loop()
            service = await loop.run_in_executor(
                None, lambda: _build_gmail_service(mailbox.credentials_json)
            )
        except Exception as exc:
            logger.error("Gmail auth failed for %s: %s", mailbox.email_address, exc)
            return {"error": str(exc), "fetched": 0, "new_rfq": 0, "skipped": 0,
                    "errors": 0, "available": 0, "needs_reauth": True}

        counters: Dict[str, Any] = {"fetched": 0, "new_rfq": 0, "skipped": 0,
                                    "errors": 0, "available": 0, "needs_reauth": False}

        # List messages (newest first, inbox only) — run blocking call in thread
        list_params: Dict[str, Any] = {
            "userId": "me",
            "maxResults": max_messages,
            "labelIds": ["INBOX"],
        }

        try:
            resp = await loop.run_in_executor(
                None, lambda: service.users().messages().list(**list_params).execute()
            )
        except Exception as exc:
            logger.error("Gmail list failed for %s: %s", mailbox.email_address, exc)
            return {**counters, "error": str(exc), "needs_reauth": True}

        messages = resp.get("messages", [])
        counters["available"] = len(messages)

        # Check which gmail_message_ids are already stored
        existing_ids_result = await self.db.execute(
            select(RFQEmail.gmail_message_id)
        )
        existing_ids = {r for r in existing_ids_result.scalars().all()}

        for msg_ref in messages:
            mid = msg_ref["id"]
            if mid in existing_ids:
                counters["skipped"] += 1
                continue

            try:
                raw = await loop.run_in_executor(
                    None,
                    lambda m=mid: service.users().messages().get(
                        userId="me", id=m, format="full"
                    ).execute()
                )
            except Exception as exc:
                err_str = str(exc)
                logger.warning("Could not fetch message %s: %s", mid, err_str)
                counters["errors"] += 1
                # Detect scope restriction — mark mailbox as needing re-auth
                if "Metadata scope" in err_str or ("403" in err_str and "scope" in err_str.lower()):
                    counters["needs_reauth"] = True
                continue

            parsed = _parse_message(raw)
            email_type = classify_email_type(
                parsed["subject"] or "",
                parsed["body_text"] or "",
            )

            email_record = RFQEmail(
                gmail_message_id=mid,
                gmail_thread_id=parsed["gmail_thread_id"],
                mailbox_id=mailbox.id,
                mailbox_email=mailbox.email_address,
                subject=parsed["subject"],
                sender_email=parsed["sender_email"],
                sender_name=parsed["sender_name"],
                recipients=parsed["recipients"],
                body_text=parsed["body_text"],
                body_html=parsed["body_html"],
                received_at=parsed["received_at"],
                labels=parsed["labels"],
                email_type=email_type,
                is_processed=False,
            )
            self.db.add(email_record)
            await self.db.flush()

            # Store attachment stubs (data downloaded on demand)
            for att in parsed["attachments"]:
                att_record = RFQAttachment(
                    email_id=email_record.id,
                    gmail_attachment_id=att["gmail_attachment_id"],
                    original_filename=att["filename"],
                    mime_type=att["mime_type"],
                    file_size=att["file_size"],
                    file_category=_guess_file_category(att["filename"], att["mime_type"]),
                    extraction_status="pending",
                )
                self.db.add(att_record)

            counters["fetched"] += 1
            if email_type in ("rfq", "revision"):
                counters["new_rfq"] += 1
                # Enqueue email processing to create RFQ + download attachments
                from app.tasks.rfq_tasks import enqueue
                await enqueue(
                    self.db,
                    "process_email",
                    "email",
                    email_record.id,
                    priority=2,
                )

        # Update last synced timestamp
        mailbox.last_synced = datetime.utcnow()
        await self.db.flush()

        return counters

    async def download_attachment(
        self,
        attachment: RFQAttachment,
        mailbox: GmailCredential,
        dest_dir: str,
    ) -> Optional[str]:
        """Download a Gmail attachment to local storage, return file path."""
        import os, aiofiles, asyncio  # type: ignore

        if not attachment.gmail_attachment_id or not mailbox.credentials_json:
            return None

        # Need the parent email's gmail_message_id
        result = await self.db.execute(
            select(RFQEmail).where(RFQEmail.id == attachment.email_id)
        )
        email = result.scalar_one_or_none()
        if not email:
            return None

        try:
            loop = asyncio.get_event_loop()
            service = await loop.run_in_executor(
                None, lambda: _build_gmail_service(mailbox.credentials_json)
            )
            att_data = await loop.run_in_executor(
                None,
                lambda: service.users().messages().attachments().get(
                    userId="me",
                    messageId=email.gmail_message_id,
                    id=attachment.gmail_attachment_id,
                ).execute()
            )
        except Exception as exc:
            logger.error("Attachment download failed: %s", exc)
            return None

        raw_data = base64.urlsafe_b64decode(att_data["data"] + "==")
        os.makedirs(dest_dir, exist_ok=True)

        import uuid
        safe_name = f"{uuid.uuid4()}_{attachment.original_filename}"
        filepath = os.path.join(dest_dir, safe_name)

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(raw_data)

        return filepath


def _guess_file_category(filename: str, mime_type: str) -> str:
    """Quick rule-based file category from filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("pdf",):
        return "pdf"
    if ext in ("xlsx", "xls", "csv"):
        return "excel"
    if ext in ("doc", "docx"):
        return "word"
    if ext in ("dwg", "dxf"):
        return "dwg"
    if ext in ("zip", "rar", "7z", "tar", "gz"):
        return "zip"
    if ext in ("jpg", "jpeg", "png", "tif", "tiff", "bmp"):
        return "image"
    if "pdf" in mime_type:
        return "pdf"
    if "excel" in mime_type or "spreadsheet" in mime_type:
        return "excel"
    if "word" in mime_type:
        return "word"
    return "other"
