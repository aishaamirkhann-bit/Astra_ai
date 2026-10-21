"""Add B2B sourcing, distribution ledger, and vendor subscription records."""
from alembic import op
import sqlalchemy as sa

revision = "20261021_20"
down_revision = "20261021_19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "b2b_bids",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("target_budget", sa.Float(), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_b2b_bid_quantity"),
        sa.CheckConstraint("target_budget > 0", name="ck_b2b_bid_target_budget"),
        sa.CheckConstraint("delivery_days > 0", name="ck_b2b_bid_delivery_days"),
        sa.CheckConstraint("status IN ('open', 'awarded', 'cancelled', 'closed')", name="ck_b2b_bid_status"),
    )
    op.create_index("ix_b2b_bids_buyer_id", "b2b_bids", ["buyer_id"])
    op.create_index("ix_b2b_bids_status_created", "b2b_bids", ["status", "created_at"])
    op.create_table(
        "vendor_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bid_id", sa.Integer(), sa.ForeignKey("b2b_bids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offered_price", sa.Float(), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=False),
        sa.Column("ai_match_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("commission_rate", sa.Float(), nullable=False),
        sa.Column("commission_amount", sa.Float(), nullable=False),
        sa.Column("vendor_net_payout", sa.Float(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("offered_price > 0", name="ck_vendor_quote_price"),
        sa.CheckConstraint("delivery_days > 0", name="ck_vendor_quote_delivery_days"),
        sa.CheckConstraint("ai_match_score >= 0 AND ai_match_score <= 100", name="ck_vendor_quote_match_score"),
        sa.CheckConstraint("commission_rate >= 0.01 AND commission_rate <= 0.02", name="ck_vendor_quote_commission_rate"),
        sa.CheckConstraint("commission_amount >= 0 AND vendor_net_payout >= 0", name="ck_vendor_quote_commission_amounts"),
        sa.CheckConstraint("status IN ('submitted', 'awarded', 'declined', 'withdrawn')", name="ck_vendor_quote_status"),
        sa.UniqueConstraint("bid_id", "vendor_id", name="uq_vendor_quote_bid_vendor"),
    )
    op.create_index("ix_vendor_quotes_bid_id", "vendor_quotes", ["bid_id"])
    op.create_index("ix_vendor_quotes_vendor_id", "vendor_quotes", ["vendor_id"])
    op.create_index("ix_vendor_quotes_bid_score", "vendor_quotes", ["bid_id", "ai_match_score"])
    op.create_table(
        "distribution_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("distributor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retailer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Text(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_type", sa.String(length=24), nullable=False, server_default="sale"),
        sa.Column("platform_commission_rate", sa.Float(), nullable=False, server_default="0.01"),
        sa.Column("commission_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("khata_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reference", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("platform_commission_rate >= 0.01 AND platform_commission_rate <= 0.02", name="ck_distribution_commission_rate"),
        sa.CheckConstraint("entry_type IN ('sale', 'repayment')", name="ck_distribution_entry_type"),
        sa.CheckConstraint("commission_amount >= 0 AND credit_amount >= 0 AND khata_amount >= 0 AND credit_limit >= 0", name="ck_distribution_nonnegative_amounts"),
    )
    op.create_index("ix_distribution_ledger_distributor_id", "distribution_ledger", ["distributor_id"])
    op.create_index("ix_distribution_ledger_retailer_id", "distribution_ledger", ["retailer_id"])
    op.create_index("ix_distribution_ledger_product_id", "distribution_ledger", ["product_id"])
    op.create_index("ix_distribution_retailer_created", "distribution_ledger", ["retailer_id", "created_at"])
    op.create_table(
        "vendor_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("monthly_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_payment"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tier IN ('Basic', 'Pro', 'Enterprise')", name="ck_vendor_subscription_tier"),
        sa.CheckConstraint("monthly_price >= 0", name="ck_vendor_subscription_price"),
        sa.CheckConstraint("status IN ('active', 'pending_payment', 'cancelled')", name="ck_vendor_subscription_status"),
    )
    op.create_index("ix_vendor_subscriptions_vendor_id", "vendor_subscriptions", ["vendor_id"])
    op.create_index("ix_vendor_subscription_vendor_status", "vendor_subscriptions", ["vendor_id", "status"])


def downgrade() -> None:
    op.drop_table("vendor_subscriptions")
    op.drop_table("distribution_ledger")
    op.drop_table("vendor_quotes")
    op.drop_table("b2b_bids")
