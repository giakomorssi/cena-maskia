"""add standing_rows, calendar_rounds, calendar_matches

Revision ID: 0004_standings_and_calendar
Revises: 0003_players_and_trades
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_standings_and_calendar"
down_revision = "0003_players_and_trades"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "standing_rows",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(length=160), nullable=False),
        sa.Column("played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals_for", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals_against", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goal_diff", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "season_id", "position", name="uq_standing_season_position"
        ),
    )

    op.create_table(
        "calendar_rounds",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("league_round", sa.Integer(), nullable=False),
        sa.Column("serie_a_round", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "season_id", "league_round", name="uq_calendar_season_round"
        ),
    )

    op.create_table(
        "calendar_matches",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "round_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendar_rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("home_team", sa.String(length=160), nullable=False),
        sa.Column("away_team", sa.String(length=160), nullable=False),
        sa.Column("home_score", sa.Float(), nullable=True),
        sa.Column("away_score", sa.Float(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("calendar_matches")
    op.drop_table("calendar_rounds")
    op.drop_table("standing_rows")
