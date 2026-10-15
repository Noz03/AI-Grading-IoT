"""Module 5 grading evidence and revisions.

Revision ID: c5e60f9b12ab
Revises: bb99436f70a4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c5e60f9b12ab"
down_revision = "bb99436f70a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("submissions", sa.Column("data_evidence", postgresql.JSONB(), nullable=True))
    op.add_column("submissions", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("grading_results", sa.Column("data_evaluation", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("grading_results", "data_evaluation")
    op.drop_column("submissions", "revision")
    op.drop_column("submissions", "data_evidence")
