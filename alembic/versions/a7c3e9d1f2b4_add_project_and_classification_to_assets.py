"""add project_id and classification to assets; make user_id nullable

Release 1 of PRD 0006 (additive). Adds nullable columns with no server default,
so rows inserted by the previous release stay legacy (NULL classification).
user_id becomes nullable so deleting an uploader does not require deleting their
project documents; the ORM cascade is removed in the same release.

Revision ID: a7c3e9d1f2b4
Revises: f3a1c2e4d5b6
Create Date: 2026-10-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a7c3e9d1f2b4"
down_revision: Union[str, None] = "f3a1c2e4d5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("classification", sa.String(), nullable=True),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.alter_column("assets", "user_id", existing_type=postgresql.UUID(), nullable=True)


def downgrade() -> None:
    # Fails if any asset has lost its uploader (user_id NULL) since this release.
    op.alter_column(
        "assets", "user_id", existing_type=postgresql.UUID(), nullable=False
    )
    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_column("assets", "classification")
    op.drop_column("assets", "project_id")
