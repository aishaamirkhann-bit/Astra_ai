"""Bind financial consent to order details and give consent a short expiry."""
from alembic import op
import sqlalchemy as sa


revision = "20261021_14"
down_revision = "20261014_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_consent_logs", sa.Column("order_snapshot_hash", sa.String(length=64), nullable=True))
    op.add_column("financial_consent_logs", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("financial_consent_logs", "expires_at")
    op.drop_column("financial_consent_logs", "order_snapshot_hash")
