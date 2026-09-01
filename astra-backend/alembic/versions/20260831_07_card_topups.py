"""Card top-ups: Stripe PaymentIntents that settle into user wallets."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_07"
down_revision = "20260831_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_topups",
        sa.Column("intent_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="requires_payment"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_card_topups_user_id", "card_topups", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_card_topups_user_id", table_name="card_topups")
    op.drop_table("card_topups")
