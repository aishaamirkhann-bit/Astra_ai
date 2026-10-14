"""Track seller listing activation state."""
from alembic import op
import sqlalchemy as sa


revision = "20261014_11"
down_revision = "20261014_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("listing_status", sa.String(length=10), server_default="active", nullable=False))


def downgrade() -> None:
    op.drop_column("products", "listing_status")
