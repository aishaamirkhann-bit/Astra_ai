"""Add barcode catalog metadata to products."""
from alembic import op
import sqlalchemy as sa


revision = "20261013_09"
down_revision = "20260903_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("barcode", sa.String(length=14), nullable=True))
    op.add_column("products", sa.Column("barcode_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("brand", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("products", sa.Column("subcategory", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("products", sa.Column("color", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("products", sa.Column("size", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("products", sa.Column("variant", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("products", sa.Column("specifications", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("products", sa.Column("quality_tags", sa.Text(), nullable=False, server_default="[]"))
    op.create_index("ix_products_barcode", "products", ["barcode"])


def downgrade() -> None:
    op.drop_index("ix_products_barcode", table_name="products")
    op.drop_column("products", "quality_tags")
    op.drop_column("products", "specifications")
    op.drop_column("products", "variant")
    op.drop_column("products", "size")
    op.drop_column("products", "color")
    op.drop_column("products", "subcategory")
    op.drop_column("products", "brand")
    op.drop_column("products", "barcode_verified")
    op.drop_column("products", "barcode")
