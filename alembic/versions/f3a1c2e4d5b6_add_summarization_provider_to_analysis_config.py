"""add summarization provider to analysis config

Revision ID: f3a1c2e4d5b6
Revises: e8d324039ef2
Create Date: 2026-06-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a1c2e4d5b6"
down_revision: Union[str, None] = "e8d324039ef2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_configs",
        sa.Column("summarization_provider", sa.String(), nullable=True),
    )
    op.add_column(
        "analysis_configs",
        sa.Column(
            "summarization_provider_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("analysis_configs", "summarization_provider_params")
    op.drop_column("analysis_configs", "summarization_provider")
