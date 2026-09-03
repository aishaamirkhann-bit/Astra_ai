"""Persist AI negotiation sessions and their offer rounds."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_06"
down_revision = "20260831_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "negotiation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("final_price", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_negotiation_sessions_user_id", "negotiation_sessions", ["user_id"])
    op.create_index("ix_negotiation_sessions_product_id", "negotiation_sessions", ["product_id"])
    op.create_index("ix_negotiation_sessions_status", "negotiation_sessions", ["status"])
    op.create_table(
        "negotiation_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("negotiation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("buyer_offer", sa.Float(), nullable=False),
        sa.Column("seller_ask", sa.Float(), nullable=False),
        sa.Column("counter_offer", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False, server_default="rules"),
        sa.Column("reasoning_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_negotiation_rounds_session_id", "negotiation_rounds", ["session_id"])


def downgrade() -> None:
    op.drop_table("negotiation_rounds")
    op.drop_table("negotiation_sessions")
