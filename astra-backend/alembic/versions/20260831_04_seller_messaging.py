"""Seller-buyer direct messaging threads and messages."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_04"
down_revision = "20260831_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("seller_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Text(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("buyer_id", "seller_id", "product_id", name="uq_conversation_party_product"),
    )
    op.create_index("ix_seller_conversations_buyer", "seller_conversations", ["buyer_id"])
    op.create_index("ix_seller_conversations_seller", "seller_conversations", ["seller_id"])
    op.create_index("ix_seller_conversations_product", "seller_conversations", ["product_id"])
    op.create_table("direct_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("seller_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_direct_messages_conversation", "direct_messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_table("direct_messages")
    op.drop_table("seller_conversations")
