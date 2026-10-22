"""Add confirmed return requests and seller-configured negotiation floors."""
from alembic import op
import sqlalchemy as sa


revision = "20261021_17"
down_revision = "20261021_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("seller_price_floor", sa.Float(), nullable=False, server_default="0"))
    op.execute("UPDATE products SET seller_price_floor = base_price WHERE seller_price_floor <= 0")
    op.create_table(
        "order_return_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", sa.String(length=16), nullable=False, server_default="return"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending_review"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_return_requests_order_id", "order_return_requests", ["order_id"])
    op.create_index("ix_order_return_requests_user_id", "order_return_requests", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_order_return_requests_user_id", table_name="order_return_requests")
    op.drop_index("ix_order_return_requests_order_id", table_name="order_return_requests")
    op.drop_table("order_return_requests")
    op.drop_column("products", "seller_price_floor")
