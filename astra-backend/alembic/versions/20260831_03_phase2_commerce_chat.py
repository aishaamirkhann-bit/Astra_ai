"""Phase 2 cart variants, order storage, and persisted AI chat."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_03"
down_revision = "20260830_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS keeps these safe on fresh databases where the baseline
    # create_all already produced the storage columns.
    op.execute("ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS storage TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS storage TEXT NOT NULL DEFAULT ''")
    op.create_table("chat_conversations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_chat_conversations_user", "chat_conversations", ["user_id", "created_at"])
    op.create_table("chat_messages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.Text(), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("card_type", sa.Text(), nullable=True), sa.Column("card_payload", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_chat_messages_conversation", "chat_messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
    op.drop_column("orders", "storage")
    op.drop_column("cart_items", "storage")
