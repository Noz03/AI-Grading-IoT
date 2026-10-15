"""Persist Vision evaluations separately from Code and Data.

Revision ID: d6a14b0f6e21
Revises: c5e60f9b12ab
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d6a14b0f6e21"
down_revision = "c5e60f9b12ab"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("grading_results", sa.Column("vision_evaluation", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("grading_results", "vision_evaluation")
