"""Initial users, links, click events and daily statistics."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_url", sa.String(4096), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_links_owner_id", "links", ["owner_id"])
    op.create_table(
        "click_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "link_id", sa.Uuid(), sa.ForeignKey("links.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_click_events_link_time", "click_events", ["link_id", "clicked_at"])
    op.create_table(
        "daily_link_stats",
        sa.Column(
            "link_id", sa.Uuid(), sa.ForeignKey("links.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("clicks", sa.BigInteger(), nullable=False),
    )


def downgrade():
    op.drop_table("daily_link_stats")
    op.drop_table("click_events")
    op.drop_table("links")
    op.drop_table("users")
