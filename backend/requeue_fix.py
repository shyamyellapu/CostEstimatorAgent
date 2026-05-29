"""
One-time fix: reset extraction_status and re-queue classify+extract tasks
for all rfq_attachments with no storage_path (Gmail attachments never downloaded).
Also queues process_email for any unprocessed RFQ emails.
"""
import asyncio
import sys
sys.path.insert(0, r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\backend')

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import RFQAttachment, RFQEmail, RFQRecord
from app.tasks.rfq_tasks import enqueue


async def fix():
    async with AsyncSessionLocal() as db:
        async with db.begin():
            # 1. Queue process_email for unprocessed RFQ emails
            email_res = await db.execute(
                select(RFQEmail).where(
                    RFQEmail.is_processed == False,
                    RFQEmail.email_type.in_(["rfq", "revision"]),
                )
            )
            emails = email_res.scalars().all()
            for email in emails:
                await enqueue(db, "process_email", "email", email.id, priority=1)
                print(f"  Queued process_email for: {email.subject[:60] if email.subject else email.id}")

            # 2. Re-queue classify+extract for attachments with no storage_path but linked to RFQ
            att_res = await db.execute(
                select(RFQAttachment).where(
                    RFQAttachment.storage_path == None,
                    RFQAttachment.rfq_id != None,
                )
            )
            atts = att_res.scalars().all()
            for att in atts:
                att.extraction_status = "pending"
                await enqueue(db, "classify_attachment", "attachment", att.id, priority=2)
                await enqueue(db, "extract_attachment", "attachment", att.id, priority=3)
                print(f"  Re-queued extract for: {att.original_filename}")

            print(f"\nDone: {len(emails)} process_email, {len(atts)} classify+extract tasks queued.")


asyncio.run(fix())
