"""Password-reset OTP columns and order escrow lifecycle status."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_05"
down_revision = "20260831_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("reset_code_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("reset_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS escrow_status VARCHAR(20) NOT NULL DEFAULT 'HELD'")


def downgrade() -> None:
    op.drop_column("orders", "escrow_status")
    op.drop_column("users", "reset_attempts")
    op.drop_column("users", "reset_expires_at")
    op.drop_column("users", "reset_code_hash")
