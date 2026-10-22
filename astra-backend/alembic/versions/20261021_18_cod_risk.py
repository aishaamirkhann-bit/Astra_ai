"""Persist advisory COD confirmation events."""
from alembic import op
import sqlalchemy as sa

revision = "20261021_18"
down_revision = "20261021_17"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("cod_risk_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_cod_risk_events_order_id", "cod_risk_events", ["order_id"])
    op.create_index("ix_cod_risk_events_buyer_id", "cod_risk_events", ["buyer_id"])
    op.create_index("ix_cod_risk_events_seller_id", "cod_risk_events", ["seller_id"])

def downgrade() -> None:
    op.drop_index("ix_cod_risk_events_seller_id", table_name="cod_risk_events")
    op.drop_index("ix_cod_risk_events_buyer_id", table_name="cod_risk_events")
    op.drop_index("ix_cod_risk_events_order_id", table_name="cod_risk_events")
    op.drop_table("cod_risk_events")
