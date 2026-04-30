"""SQLAlchemy models for the Fantacalcio league."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # es. "2025/26"
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    account_username: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    manager_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    home_city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BalanceSheet(Base):
    """Bilancio di una squadra in una stagione."""

    __tablename__ = "balance_sheets"
    __table_args__ = (
        UniqueConstraint("team_id", "season_id", name="uq_balance_team_season"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Aggregati calcolati
    total_ricavi: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_costi: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_ammortamenti: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    total_plus_minus: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    utile: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sanction_level: Mapped[str] = mapped_column(
        String(20), default="none", nullable=False
    )
    sanction_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sanction_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entries: Mapped[list["BalanceEntry"]] = relationship(
        "BalanceEntry", back_populates="balance_sheet", cascade="all, delete-orphan"
    )
    team: Mapped[Team] = relationship("Team")
    season: Mapped[Season] = relationship("Season")


class BalanceEntry(Base):
    """Singola voce di bilancio (riga estratta dall'Excel)."""

    __tablename__ = "balance_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    balance_sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("balance_sheets.id", ondelete="CASCADE"),
        nullable=False,
    )
    section: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    balance_sheet: Mapped[BalanceSheet] = relationship(
        "BalanceSheet", back_populates="entries"
    )


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    from_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    to_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    player_name: Mapped[str] = mapped_column(String(200), nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="cessione", nullable=False)
    transfer_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Fine(Base):
    __tablename__ = "fines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fine_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Honor(Base):
    __tablename__ = "honors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    trophy: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NewsPost(Base):
    __tablename__ = "news_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Poll(Base):
    __tablename__ = "polls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closes_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    options: Mapped[list["PollOption"]] = relationship(
        "PollOption", back_populates="poll", cascade="all, delete-orphan"
    )


class PollOption(Base):
    __tablename__ = "poll_options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    poll_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("polls.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    votes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    poll: Mapped[Poll] = relationship("Poll", back_populates="options")


class PollVote(Base):
    __tablename__ = "poll_votes"
    __table_args__ = (UniqueConstraint("poll_id", "voter_hash", name="uq_poll_voter"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    poll_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("polls.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("poll_options.id", ondelete="CASCADE"),
        nullable=False,
    )
    voter_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ============================================================
# Roster (Players)
# ============================================================
class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    fascia: Mapped[str] = mapped_column(String(20), nullable=False, default="1_9")
    salary: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    market_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contract_years_total: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    contract_years_remaining: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    acquisition_type: Mapped[str] = mapped_column(
        String(40), default="owned", nullable=False
    )
    acquisition_season_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    team: Mapped[Team] = relationship("Team", foreign_keys=[team_id])
    season: Mapped[Season] = relationship("Season", foreign_keys=[season_id])


# ============================================================
# Trade Proposals (Mercato workflow)
# ============================================================
class TradeProposal(Base):
    __tablename__ = "trade_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    from_team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    to_team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="swap")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    cash_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ratified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["TradeProposalItem"]] = relationship(
        "TradeProposalItem",
        back_populates="proposal",
        cascade="all, delete-orphan",
    )
    from_team: Mapped[Team] = relationship("Team", foreign_keys=[from_team_id])
    to_team: Mapped[Team] = relationship("Team", foreign_keys=[to_team_id])
    season: Mapped[Season] = relationship("Season")


class TradeProposalItem(Base):
    __tablename__ = "trade_proposal_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trade_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(30), nullable=False)
    acquisition_type_after: Mapped[str] = mapped_column(
        String(40), nullable=False, default="owned"
    )
    contract_years_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_value_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    proposal: Mapped[TradeProposal] = relationship(
        "TradeProposal", back_populates="items"
    )
    player: Mapped[Player] = relationship("Player")
