"""Baseline the non-wallet Astra schema for fresh PostgreSQL deployments."""
from alembic import op

from app.core.database import Base
import app.models  # noqa: F401

revision = "20260830_00"
down_revision = None
branch_labels = None
depends_on = None

MIGRATED_TABLES = {"user_wallets", "wallet_transactions", "financial_consent_logs", "chat_conversations", "chat_messages", "seller_conversations", "direct_messages"}


def upgrade() -> None:
    bind = op.get_bind()
    tables = [table for table in Base.metadata.sorted_tables if table.name not in MIGRATED_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    # Core tables may predate Alembic; never destructively drop them here.
    pass
