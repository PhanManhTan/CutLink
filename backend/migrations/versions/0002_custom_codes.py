"""Allow custom short-link endings while preserving existing eight-character codes."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("links", "code", existing_type=sa.String(8), type_=sa.String(64))


def downgrade():
    op.alter_column("links", "code", existing_type=sa.String(64), type_=sa.String(8))
