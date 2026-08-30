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
    # IF NOT EXISTS keeps this migration safe on fresh databases where the
    # baseline create_all already produced these columns.
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipped_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITH TIME ZONE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications (user_id, created_at)")


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "shipped_at")
