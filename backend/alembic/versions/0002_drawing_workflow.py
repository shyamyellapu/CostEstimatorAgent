"""Add drawing workflow tables

Revision ID: 0002_drawing_workflow
Revises: 0001_initial_postgresql
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_drawing_workflow"
down_revision = "0001_initial_postgresql"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── drawing_pages ──────────────────────────────────────────────────────
    op.create_table(
        "drawing_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("page_type", sa.String(80), nullable=True),
        sa.Column("page_storage_path", sa.String(1000), nullable=True),
        sa.Column("image_storage_path", sa.String(1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("processing_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_drawing_page_job_type", "drawing_pages", ["job_id", "page_type"])
    op.create_index("idx_drawing_page_status", "drawing_pages", ["job_id", "processing_status"])

    # ── bom_items ──────────────────────────────────────────────────────────
    op.create_table(
        "bom_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("item_no", sa.String(50), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("section_type", sa.String(100), nullable=True),
        sa.Column("section_size", sa.String(100), nullable=True),
        sa.Column("qty", sa.Float(), nullable=True),
        sa.Column("length_mm", sa.Float(), nullable=True),
        sa.Column("width_mm", sa.Float(), nullable=True),
        sa.Column("thickness_mm", sa.Float(), nullable=True),
        sa.Column("diameter_mm", sa.Float(), nullable=True),
        sa.Column("unit_weight_kg", sa.Float(), nullable=True),
        sa.Column("total_weight_kg", sa.Float(), nullable=True),
        sa.Column("material_grade", sa.String(100), nullable=True),
        sa.Column("remarks", sa.String(500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_json", JSONB(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_bom_item_job_category", "bom_items", ["job_id", "category"])
    op.create_index("idx_bom_item_review", "bom_items", ["job_id", "review_required"])

    # ── drawing_components ─────────────────────────────────────────────────
    op.create_table(
        "drawing_components",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("component_type", sa.String(100), nullable=True),
        sa.Column("component_name", sa.String(255), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("section_type", sa.String(100), nullable=True),
        sa.Column("section_size", sa.String(100), nullable=True),
        sa.Column("qty", sa.Float(), nullable=True),
        sa.Column("length_mm", sa.Float(), nullable=True),
        sa.Column("width_mm", sa.Float(), nullable=True),
        sa.Column("thickness_mm", sa.Float(), nullable=True),
        sa.Column("diameter_mm", sa.Float(), nullable=True),
        sa.Column("pipe_schedule", sa.String(50), nullable=True),
        sa.Column("material_grade", sa.String(100), nullable=True),
        sa.Column("surface_treatment", sa.String(200), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_json", JSONB(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_drawing_comp_job_type", "drawing_components", ["job_id", "component_type"])
    op.create_index("idx_drawing_comp_review", "drawing_components", ["job_id", "review_required"])

    # ── quantity_results ───────────────────────────────────────────────────
    op.create_table(
        "quantity_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("quantity_unit", sa.String(50), nullable=True),
        sa.Column("quantity_value", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column("linear_meter", sa.Float(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("calculation_method", sa.String(200), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_qty_result_job_category", "quantity_results", ["job_id", "category"])

    # ── costing_validation_results ─────────────────────────────────────────
    op.create_table(
        "costing_validation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("validation_type", sa.String(100), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_item_id", sa.String(36), nullable=True),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("actual_value", sa.Float(), nullable=True),
        sa.Column("difference_percent", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_val_result_job_severity", "costing_validation_results", ["job_id", "severity"])
    op.create_index("idx_val_result_status", "costing_validation_results", ["job_id", "status"])


def downgrade() -> None:
    op.drop_table("costing_validation_results")
    op.drop_table("quantity_results")
    op.drop_table("drawing_components")
    op.drop_table("bom_items")
    op.drop_table("drawing_pages")
