"""Persist Stripe order checkout, webhook idempotency, and seller payout ledger."""
from alembic import op
import sqlalchemy as sa


revision = "20261014_14"
down_revision = "20261014_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("otp_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "stripe_checkout_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stripe_session_id", sa.String(length=255), nullable=False),
        sa.Column("checkout_session_id", sa.Integer(), nullable=False),
        sa.Column("checkout_url", sa.Text(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["checkout_session_id"], ["checkout_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkout_session_id"),
        sa.UniqueConstraint("stripe_session_id"),
    )
    op.create_index("ix_stripe_checkout_payments_stripe_session_id", "stripe_checkout_payments", ["stripe_session_id"])
    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_table(
        "stripe_connect_accounts",
        sa.Column("seller_user_id", sa.Integer(), nullable=False),
        sa.Column("stripe_account_id", sa.String(length=255), nullable=False),
        sa.Column("details_submitted", sa.Integer(), nullable=False),
        sa.Column("charges_enabled", sa.Integer(), nullable=False),
        sa.Column("payouts_enabled", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seller_user_id"], ["seller_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("seller_user_id"),
        sa.UniqueConstraint("stripe_account_id"),
    )
    op.create_table(
        "seller_payout_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("seller_user_id", sa.Integer(), nullable=True),
        sa.Column("seller_key", sa.String(length=160), nullable=False),
        sa.Column("gross_amount", sa.Float(), nullable=False),
        sa.Column("platform_fee", sa.Float(), nullable=False),
        sa.Column("seller_amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stripe_transfer_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_user_id"], ["seller_profiles.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_seller_payout_order"),
    )
    op.create_index("ix_seller_payout_ledger_seller_user_id", "seller_payout_ledger", ["seller_user_id"])


def downgrade() -> None:
    op.drop_index("ix_seller_payout_ledger_seller_user_id", table_name="seller_payout_ledger")
    op.drop_table("seller_payout_ledger")
    op.drop_table("stripe_connect_accounts")
    op.drop_table("stripe_webhook_events")
    op.drop_index("ix_stripe_checkout_payments_stripe_session_id", table_name="stripe_checkout_payments")
    op.drop_table("stripe_checkout_payments")
    op.drop_column("users", "otp_sent_at")