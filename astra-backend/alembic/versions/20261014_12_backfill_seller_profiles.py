"""Create scorecard rows for seller accounts that predate SellerProfile."""
from alembic import op
import sqlalchemy as sa


revision = "20261014_12"
down_revision = "20261014_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "INSERT INTO seller_profiles (user_id, role, compliance_status, total_revenue) "
            "SELECT id, 'seller', 'pending', 0 FROM users WHERE role = 'seller' "
            "ON CONFLICT (user_id) DO NOTHING"
        ))
    elif connection.dialect.name == "sqlite":
        connection.execute(sa.text(
            "INSERT OR IGNORE INTO seller_profiles (user_id, role, compliance_status, total_revenue) "
            "SELECT id, 'seller', 'pending', 0 FROM users WHERE role = 'seller'"
        ))


def downgrade() -> None:
    # Profile rows may have acquired verified scores/revenue since this backfill.
    pass
