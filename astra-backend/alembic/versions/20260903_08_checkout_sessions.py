"""Persist checkout sessions and bind financial consent to them."""
from alembic import op
import sqlalchemy as sa


revision = "20260903_08"
down_revision = "20260831_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkout_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("checkout_ref", sa.String(length=40), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("shipping_address", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="awaiting_consent"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("total > 0", name="ck_checkout_session_total"),
        sa.CheckConstraint(
            "status IN ('awaiting_consent', 'reversal_window_open', 'confirmed', 'cancelled', 'expired')",
            name="ck_checkout_session_status",
        ),
    )
    op.create_index("ix_checkout_sessions_user_status", "checkout_sessions", ["user_id", "status"])
    op.create_index("ix_checkout_sessions_expires_at", "checkout_sessions", ["expires_at"])

    op.add_column("orders", sa.Column("checkout_session_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_checkout_session_id",
        "orders",
        "checkout_sessions",
        ["checkout_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_orders_checkout_session_id", "orders", ["checkout_session_id"])

    op.add_column("financial_consent_logs", sa.Column("reference_checkout_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_financial_consent_logs_reference_checkout_id",
        "financial_consent_logs",
        "checkout_sessions",
        ["reference_checkout_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_financial_consent_single_subject",
        "financial_consent_logs",
        "reference_order_id IS NULL OR reference_checkout_id IS NULL",
    )
    op.create_index(
        "ix_financial_consent_checkout_status",
        "financial_consent_logs",
        ["reference_checkout_id", "status", "consumed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_consent_checkout_status", table_name="financial_consent_logs")
    op.drop_constraint("ck_financial_consent_single_subject", "financial_consent_logs", type_="check")
    op.drop_constraint("fk_financial_consent_logs_reference_checkout_id", "financial_consent_logs", type_="foreignkey")
    op.drop_column("financial_consent_logs", "reference_checkout_id")

    op.drop_index("ix_orders_checkout_session_id", table_name="orders")
    op.drop_constraint("fk_orders_checkout_session_id", "orders", type_="foreignkey")
    op.drop_column("orders", "checkout_session_id")

    op.drop_index("ix_checkout_sessions_expires_at", table_name="checkout_sessions")
    op.drop_index("ix_checkout_sessions_user_status", table_name="checkout_sessions")
    op.drop_table("checkout_sessions")
