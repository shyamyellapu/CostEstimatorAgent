"""Initial PostgreSQL schema for Cost Estimator AI Agent.

Revision ID: 0001_initial_postgresql
Revises: 
Create Date: 2026-05-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.database import Base
import app.models  # noqa: F401  # ensure model metadata is registered

# revision identifiers, used by Alembic.
revision = "0001_initial_postgresql"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the baseline PostgreSQL schema from SQLAlchemy metadata."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop the baseline PostgreSQL schema."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
