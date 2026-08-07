"""Add customer_info_json to jobs.

Stores the customer/quotation header fields (customerName, refNo, enquiryNo,
jobNo, attention, contact) collected in the drawing-costing review UI just
before Excel generation, keyed to the job so reopening it later pre-fills the
same values instead of asking again from scratch.

Revision ID: 0005_job_customer_info
Revises: 0004_manager_and_user_role
Create Date: 2026-08-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_job_customer_info"
down_revision = "0004_manager_and_user_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("customer_info_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "customer_info_json")
