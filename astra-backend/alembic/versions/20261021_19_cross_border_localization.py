"""Persist user region and product origin country."""
from alembic import op
import sqlalchemy as sa

revision = "20261021_19"
down_revision = "20261021_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("country", sa.String(length=2), nullable=False, server_default="PK"))
    op.add_column("products", sa.Column("origin_country", sa.String(length=2), nullable=False, server_default="PK"))


def downgrade() -> None:
    op.drop_column("products", "origin_country")
    op.drop_column("users", "country")
