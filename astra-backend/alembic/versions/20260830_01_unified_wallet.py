"""Unified production wallet, transaction ledger, and single-use consent tables."""
from alembic import op
import sqlalchemy as sa

revision = "20260830_01"
down_revision = "20260830_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("user_wallets",
        sa.Column("wallet_id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"), sa.Column("available_balance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("frozen_balance", sa.Float(), nullable=False, server_default="0"), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("available_balance >= 0", name="ck_wallet_available_balance"), sa.CheckConstraint("frozen_balance >= 0", name="ck_wallet_frozen_balance"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_table("wallet_transactions",
        sa.Column("txn_id", sa.Text(), primary_key=True), sa.Column("wallet_id", sa.Integer(), nullable=False), sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("txn_type", sa.String(10), nullable=False), sa.Column("description", sa.String(240), nullable=False), sa.Column("reference_order_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_wallet_transaction_amount"), sa.CheckConstraint("txn_type IN ('Credit', 'Debit', 'Refund')", name="ck_wallet_transaction_type"),
        sa.ForeignKeyConstraint(["wallet_id"], ["user_wallets.wallet_id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["reference_order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference_order_id", "txn_type", name="uq_wallet_order_transaction_type"),
    )
    op.create_index("ix_wallet_transactions_wallet_created", "wallet_transactions", ["wallet_id", "created_at"])
    op.create_table("financial_consent_logs",
        sa.Column("consent_id", sa.Text(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("auth_method", sa.String(10), nullable=False), sa.Column("voice_transcript", sa.Text()), sa.Column("status", sa.String(10), nullable=False),
        sa.Column("reference_order_id", sa.Integer()), sa.Column("otp_code_hash", sa.Text()), sa.Column("otp_expires_at", sa.DateTime(timezone=True)),
        sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_financial_consent_amount"), sa.CheckConstraint("auth_method IN ('Voice', 'OTP')", name="ck_financial_consent_method"),
        sa.CheckConstraint("status IN ('Approved', 'Rejected', 'Flagged')", name="ck_financial_consent_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["reference_order_id"], ["orders.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_financial_consent_user_created", "financial_consent_logs", ["user_id", "created_at"])
    op.create_index("ix_financial_consent_order_status", "financial_consent_logs", ["reference_order_id", "status", "consumed_at"])


def downgrade() -> None:
    op.drop_table("financial_consent_logs")
    op.drop_table("wallet_transactions")
    op.drop_table("user_wallets")
