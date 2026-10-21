"""Bind negotiated prices to buyer approval and a single checkout order."""
from alembic import op
import sqlalchemy as sa


revision = "20261021_15"
down_revision = "20261021_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("negotiation_sessions", sa.Column("seller_id", sa.String(), nullable=False, server_default=""))
    op.add_column("negotiation_sessions", sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("negotiation_sessions", sa.Column("size", sa.Text(), nullable=False, server_default=""))
    op.add_column("negotiation_sessions", sa.Column("color", sa.Text(), nullable=False, server_default=""))
    op.add_column("negotiation_sessions", sa.Column("storage", sa.Text(), nullable=False, server_default=""))
    op.add_column("negotiation_sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("negotiation_sessions", sa.Column("buyer_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("negotiation_sessions", sa.Column("checkout_session_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("negotiation_sessions") as batch:
        batch.create_foreign_key(
            "fk_negotiation_sessions_checkout_session_id", "checkout_sessions",
            ["checkout_session_id"], ["id"], ondelete="SET NULL",
        )
    op.create_index("ix_negotiation_sessions_checkout_session_id", "negotiation_sessions", ["checkout_session_id"], unique=True)
    op.add_column("orders", sa.Column("negotiation_session_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("orders") as batch:
        batch.create_foreign_key(
            "fk_orders_negotiation_session_id", "negotiation_sessions",
            ["negotiation_session_id"], ["id"], ondelete="SET NULL",
        )
    op.create_index("ix_orders_negotiation_session_id", "orders", ["negotiation_session_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_orders_negotiation_session_id", table_name="orders")
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_negotiation_session_id", type_="foreignkey")
    op.drop_column("orders", "negotiation_session_id")
    op.drop_index("ix_negotiation_sessions_checkout_session_id", table_name="negotiation_sessions")
    with op.batch_alter_table("negotiation_sessions") as batch:
        batch.drop_constraint("fk_negotiation_sessions_checkout_session_id", type_="foreignkey")
    for column in ("checkout_session_id", "buyer_approved_at", "expires_at", "storage", "color", "size", "quantity", "seller_id"):
        op.drop_column("negotiation_sessions", column)
