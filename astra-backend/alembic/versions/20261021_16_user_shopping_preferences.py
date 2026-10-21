"""Store a minimal set of explicit, user-scoped shopping preferences."""
from alembic import op
import sqlalchemy as sa


revision = "20261021_16"
down_revision = "20261021_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopping_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("clothing_size", sa.String(length=16), nullable=True),
        sa.Column("favorite_color", sa.String(length=32), nullable=True),
        sa.Column("preferred_category", sa.String(length=80), nullable=True),
        sa.Column("budget_min", sa.Float(), nullable=True),
        sa.Column("budget_max", sa.Float(), nullable=True),
        sa.Column("shopping_preferences_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="ck_shopping_preferences_budget_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("shopping_preferences")
