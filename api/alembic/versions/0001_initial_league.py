"""initial league schema

Revision ID: 0001_initial_league
Revises:
Create Date: 2026-04-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_league"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("username", sa.String(length=50), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_is_active", "users", ["is_active"])

    # seasons
    op.create_table(
        "seasons",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("name", sa.String(length=20), nullable=False, unique=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # teams
    op.create_table(
        "teams",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("manager_name", sa.String(length=120), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # balance_sheets
    op.create_table(
        "balance_sheets",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="submitted"
        ),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("total_ricavi", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_costi", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_ammortamenti", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_plus_minus", sa.Float(), nullable=False, server_default="0"),
        sa.Column("utile", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "sanction_level",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
        sa.Column("sanction_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sanction_notes", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "season_id", name="uq_balance_team_season"),
    )

    # balance_entries
    op.create_table(
        "balance_entries",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "balance_sheet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("balance_sheets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
    )

    # transfers
    op.create_table(
        "transfers",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id"),
            nullable=True,
        ),
        sa.Column(
            "to_team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id"),
            nullable=True,
        ),
        sa.Column("player_name", sa.String(length=200), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "type", sa.String(length=30), nullable=False, server_default="cessione"
        ),
        sa.Column("transfer_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # fines
    op.create_table(
        "fines",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fine_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # honors
    op.create_table(
        "honors",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trophy", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # news_posts
    op.create_table(
        "news_posts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # polls
    op.create_table(
        "polls",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "poll_options",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "poll_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("polls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("votes_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "poll_votes",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "poll_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("polls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "option_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("poll_options.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("voter_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("poll_id", "voter_hash", name="uq_poll_voter"),
    )


def downgrade() -> None:
    op.drop_table("poll_votes")
    op.drop_table("poll_options")
    op.drop_table("polls")
    op.drop_table("news_posts")
    op.drop_table("honors")
    op.drop_table("fines")
    op.drop_table("transfers")
    op.drop_table("balance_entries")
    op.drop_table("balance_sheets")
    op.drop_table("teams")
    op.drop_table("seasons")
    op.drop_index("idx_users_is_active", table_name="users")
    op.drop_index("idx_users_username", table_name="users")
    op.drop_table("users")
