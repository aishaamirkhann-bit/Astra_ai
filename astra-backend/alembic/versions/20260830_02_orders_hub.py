"""Add fulfillment tracking timestamps and order status values."""
from alembic import op
import sqlalchemy as sa

revision = "20260830_02"
down_revision = "20260830_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'SHIPPED'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'DELIVERED'")
    op.add_column("orders", sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "shipped_at")
