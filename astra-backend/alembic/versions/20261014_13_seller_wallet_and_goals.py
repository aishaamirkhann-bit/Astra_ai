"""Add isolated seller wallet/ledger and seller sales goals."""
from alembic import op
import sqlalchemy as sa


revision = "20261014_13"
down_revision = "20261014_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seller_wallets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("available_balance", sa.Float(), server_default="0", nullable=False),
        sa.Column("pending_payouts", sa.Float(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("available_balance >= 0", name="ck_seller_wallet_available_balance"),
        sa.CheckConstraint("pending_payouts >= 0", name="ck_seller_wallet_pending_payouts"),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id"),
    )
    op.create_index("ix_seller_wallets_seller_id", "seller_wallets", ["seller_id"])
    op.create_table(
        "seller_wallet_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("seller_wallet_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("entry_type", sa.String(length=24), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_seller_wallet_entry_amount"),
        sa.CheckConstraint(
            "entry_type IN ('sale_credit', 'payout_requested', 'payout_paid', 'adjustment')",
            name="ck_seller_wallet_entry_type",
        ),
        sa.ForeignKeyConstraint(["seller_wallet_id"], ["seller_wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_seller_wallet_entries_seller_wallet_id", "seller_wallet_entries", ["seller_wallet_id"])
    op.create_index("ix_seller_wallet_entries_created_at", "seller_wallet_entries", ["created_at"])
    op.create_table(
        "seller_sales_goals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("source_goal_id", sa.Integer(), nullable=True),
        sa.Column("target_title", sa.String(length=100), nullable=False),
        sa.Column("target_amount", sa.Float(), nullable=False),
        sa.Column("current_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deadline", sa.String(length=20), nullable=True),
        sa.CheckConstraint("target_amount > 0", name="ck_seller_sales_goal_target"),
        sa.CheckConstraint("current_amount >= 0", name="ck_seller_sales_goal_current"),
        sa.ForeignKeyConstraint(["seller_id"], ["seller_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_goal_id"),
    )
    op.create_index("ix_seller_sales_goals_seller_id", "seller_sales_goals", ["seller_id"])

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "INSERT INTO seller_wallets (seller_id, available_balance, pending_payouts) "
            "SELECT user_id, 0, 0 FROM seller_profiles ON CONFLICT (seller_id) DO NOTHING"
        ))
        connection.execute(sa.text(
            "INSERT INTO seller_sales_goals (seller_id, source_goal_id, target_title, target_amount, current_amount, deadline) "
            "SELECT g.user_id, g.id, g.name, g.target_amount, COALESCE(g.allocated_amount, 0), g.deadline "
            "FROM goals g JOIN users u ON u.id = g.user_id WHERE u.role = 'seller' "
            "ON CONFLICT (source_goal_id) DO NOTHING"
        ))
    elif connection.dialect.name == "sqlite":
        connection.execute(sa.text(
            "INSERT OR IGNORE INTO seller_wallets (seller_id, available_balance, pending_payouts) "
            "SELECT user_id, 0, 0 FROM seller_profiles"
        ))
        connection.execute(sa.text(
            "INSERT OR IGNORE INTO seller_sales_goals (seller_id, source_goal_id, target_title, target_amount, current_amount, deadline) "
            "SELECT g.user_id, g.id, g.name, g.target_amount, COALESCE(g.allocated_amount, 0), g.deadline "
            "FROM goals g JOIN users u ON u.id = g.user_id WHERE u.role = 'seller'"
        ))


def downgrade() -> None:
    op.drop_index("ix_seller_sales_goals_seller_id", table_name="seller_sales_goals")
    op.drop_table("seller_sales_goals")
    op.drop_index("ix_seller_wallet_entries_created_at", table_name="seller_wallet_entries")
    op.drop_index("ix_seller_wallet_entries_seller_wallet_id", table_name="seller_wallet_entries")
    op.drop_table("seller_wallet_entries")
    op.drop_index("ix_seller_wallets_seller_id", table_name="seller_wallets")
    op.drop_table("seller_wallets")
