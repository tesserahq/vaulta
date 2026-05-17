"""add summary column to assets

Revision ID: e8d324039ef2
Revises: a4770a106706
Create Date: 2026-05-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8d324039ef2"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "summary")
