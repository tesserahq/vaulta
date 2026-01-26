"""create_clients_table

Revision ID: 1985792d2005
Revises: 2df9d70edee8
Create Date: 2025-07-10 22:08:27.439516

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1985792d2005"
down_revision: Union[str, None] = "2df9d70edee8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("client_id", sa.String, unique=True, nullable=False),
        sa.Column("secret_generated_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
    )

    # Add a partial unique index for client_id
    op.create_index(
        "uq_clients_client_id",
        "clients",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("client_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the partial unique index
    op.drop_index("uq_clients_client_id", table_name="clients")
    op.drop_table("clients")
