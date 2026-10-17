"""Persist Stripe refund reconciliation and stable seller payout identity."""
from alembic import op
import sqlalchemy as sa


revision = "20261016_15"
down_revision = "20261014_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seller_profiles", sa.Column("seller_key", sa.String(length=160), nullable=True))
    connection = op.get_bind()
    matches = connection.execute(sa.text(
        "SELECT sp.user_id, p.seller_id FROM seller_profiles sp "
        "JOIN users u ON u.id = sp.user_id JOIN products p ON p.seller_name = u.name "
        "WHERE p.seller_id IS NOT NULL AND p.seller_id != ''"
    )).all()
    user_keys: dict[int, set[str]] = {}
    key_users: dict[str, set[int]] = {}
    for user_id, seller_key in matches:
        user_keys.setdefault(user_id, set()).add(seller_key)
        key_users.setdefault(seller_key, set()).add(user_id)
    for user_id, keys in user_keys.items():
        if len(keys) == 1:
            seller_key = next(iter(keys))
            if len(key_users[seller_key]) == 1:
                connection.execute(sa.text(
                    "UPDATE seller_profiles SET seller_key = :seller_key WHERE user_id = :user_id"
                ), {"seller_key": seller_key, "user_id": user_id})
    op.create_index("ix_seller_profiles_seller_key", "seller_profiles", ["seller_key"], unique=True)

    op.add_column("seller_payout_ledger", sa.Column("transfer_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "stripe_refunds",
        sa.Column("refund_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_checkout_payment_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("amount_paisa", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["stripe_checkout_payment_id"], ["stripe_checkout_payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("refund_id"),
    )
    op.create_index("ix_stripe_refunds_stripe_checkout_payment_id", "stripe_refunds", ["stripe_checkout_payment_id"])
    op.create_index("ix_stripe_refunds_order_id", "stripe_refunds", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_stripe_refunds_order_id", table_name="stripe_refunds")
    op.drop_index("ix_stripe_refunds_stripe_checkout_payment_id", table_name="stripe_refunds")
    op.drop_table("stripe_refunds")
    op.drop_column("seller_payout_ledger", "transfer_attempts")
    op.drop_index("ix_seller_profiles_seller_key", table_name="seller_profiles")
    op.drop_column("seller_profiles", "seller_key")