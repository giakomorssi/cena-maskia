"""add players, trade_proposals and trade_proposal_items

Revision ID: 0003_players_and_trades
Revises: 0002_team_profiles
Create Date: 2026-04-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_players_and_trades"
down_revision = "0002_team_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "players",
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
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "fascia", sa.String(length=20), nullable=False, server_default="1_19"
        ),
        sa.Column("salary", sa.Float(), nullable=False, server_default="0"),
        sa.Column("market_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "contract_years_total", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "contract_years_remaining", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "acquisition_type",
            sa.String(length=40),
            nullable=False,
            server_default="owned",
        ),
        sa.Column(
            "acquisition_season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    )
    op.create_index("idx_players_team_season", "players", ["team_id", "season_id"])

    op.create_table(
        "trade_proposals",
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
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="swap"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="proposed"
        ),
        sa.Column("cash_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ratified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_trade_proposals_status", "trade_proposals", ["status", "season_id"]
    )

    op.create_table(
        "trade_proposal_items",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trade_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(length=30), nullable=False),
        sa.Column(
            "acquisition_type_after",
            sa.String(length=40),
            nullable=False,
            server_default="owned",
        ),
        sa.Column("contract_years_after", sa.Integer(), nullable=True),
        sa.Column("salary_after", sa.Float(), nullable=True),
        sa.Column("market_value_after", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("trade_proposal_items")
    op.drop_index("idx_trade_proposals_status", table_name="trade_proposals")
    op.drop_table("trade_proposals")
    op.drop_index("idx_players_team_season", table_name="players")
    op.drop_table("players")
