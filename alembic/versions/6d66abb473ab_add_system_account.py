"""add service account

Revision ID: 6d66abb473ab
Revises: a4770a106706
Create Date: 2026-02-02 15:47:33.921211

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6d66abb473ab"
down_revision: Union[str, None] = "a4770a106706"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("service_account", sa.Boolean, default=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "service_account")
