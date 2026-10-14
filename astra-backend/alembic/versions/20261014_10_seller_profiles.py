"""Add seller profile scorecard."""
from alembic import op
import sqlalchemy as sa


revision = "20261014_10"
down_revision = "20261013_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seller_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), server_default="seller", nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=True),
        sa.Column("compliance_status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("authenticity_score", sa.Float(), nullable=True),
        sa.Column("total_revenue", sa.Float(), server_default="0", nullable=False),
        sa.CheckConstraint("role = 'seller'", name="ck_seller_profile_role"),
        sa.CheckConstraint("total_revenue >= 0", name="ck_seller_profile_revenue"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_seller_profiles_user_id", "seller_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_seller_profiles_user_id", table_name="seller_profiles")
    op.drop_table("seller_profiles")
