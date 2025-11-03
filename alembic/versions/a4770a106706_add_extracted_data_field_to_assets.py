"""Add extracted_data field to assets

Revision ID: a4770a106706
Revises: 1985792d2005
Create Date: 2025-11-04 10:08:57.773850

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4770a106706"
down_revision: Union[str, None] = "1985792d2005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("assets", sa.Column("extracted_data", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("assets", "extracted_data")
