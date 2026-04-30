"""Pydantic schemas for league entities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Season ----------
class SeasonBase(BaseModel):
    name: str = Field(..., max_length=20)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False


class SeasonCreate(SeasonBase):
    pass


class SeasonUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None


class SeasonResponse(_ORM, SeasonBase):
    id: UUID
    created_at: datetime


# ---------- Team ----------
class TeamBase(BaseModel):
    name: str = Field(..., max_length=120)
    manager_name: Optional[str] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None


class TeamCreate(TeamBase):
    account_username: Optional[str] = Field(default=None, max_length=80)
    password: Optional[str] = Field(default=None, min_length=3, max_length=128)
    profile_bio: Optional[str] = None
    home_city: Optional[str] = Field(default=None, max_length=120)


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    manager_name: Optional[str] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None
    account_username: Optional[str] = Field(default=None, max_length=80)
    password: Optional[str] = Field(default=None, min_length=3, max_length=128)
    profile_bio: Optional[str] = None
    home_city: Optional[str] = Field(default=None, max_length=120)
    is_active: Optional[bool] = None


class TeamResponse(_ORM, TeamBase):
    id: UUID
    created_at: datetime


class TeamAccountResponse(TeamResponse):
    account_username: str
    profile_bio: Optional[str] = None
    home_city: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None


class TeamSelfUpdate(BaseModel):
    manager_name: Optional[str] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None
    profile_bio: Optional[str] = None
    home_city: Optional[str] = None


class TeamLoginRequest(BaseModel):
    username: str
    password: str


class TeamLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    team: TeamAccountResponse


class TeamDashboardResponse(BaseModel):
    team: TeamAccountResponse
    current_season: Optional[SeasonResponse] = None
    latest_balance: Optional[BalanceSheetResponse] = None
    recent_balances: list[BalanceSheetResponse] = []
    fines: list[FineResponse] = []
    transfers: list[TransferResponse] = []
    honors: list[HonorResponse] = []
    unpaid_fines_total: float = 0.0
    has_uploaded_current_balance: bool = False
    current_balance_status: Optional[str] = None
    roster_summary: Optional["RosterSummary"] = None
    pending_incoming_trades: int = 0
    pending_outgoing_trades: int = 0


class TeamAdminStatusResponse(BaseModel):
    team_id: UUID
    team_name: str
    account_username: str
    manager_name: Optional[str] = None
    current_season_name: Optional[str] = None
    profile_complete: bool
    has_uploaded_current_balance: bool
    current_balance_status: Optional[str] = None
    latest_submitted_at: Optional[datetime] = None
    latest_sanction_level: Optional[str] = None
    latest_sanction_points: Optional[int] = None
    unpaid_fines_total: float = 0.0
    roster_count: int = 0
    anomalies: list["BalanceIssueResponse"] = []
    is_ok: bool


# ---------- Balance ----------
class BalanceEntryResponse(_ORM):
    id: UUID
    section: str
    label: str
    amount: float
    meta: Optional[dict] = None


class BalanceEntryDraftResponse(BaseModel):
    section: str
    label: str
    amount: float
    meta: Optional[dict] = None


class BalanceSheetResponse(_ORM):
    id: UUID
    team_id: UUID
    season_id: UUID
    status: str
    file_url: Optional[str]
    total_ricavi: float
    total_costi: float
    total_ammortamenti: float
    total_plus_minus: float
    utile: float
    sanction_level: str
    sanction_points: int
    sanction_notes: Optional[str]
    submitted_at: datetime
    entries: list[BalanceEntryResponse] = []


class BalanceIssueResponse(BaseModel):
    code: str
    label: str
    detail: str
    severity: Literal["info", "warning", "critical"] = "warning"


class BalanceStadiumOptionResponse(BaseModel):
    id: str
    name: str
    city: str
    revenue: float
    cost: float
    description: str


class BalanceGuidedFieldResponse(BaseModel):
    section: Literal["ricavi", "costi", "ammortamenti", "plus_minus"]
    label: str
    amount: float = 0.0
    meta: Optional[dict] = None
    description: str


class BalanceGuidedResponse(BaseModel):
    balance: BalanceSheetResponse
    selected_stadium_id: Optional[str] = None
    stadiums: list[BalanceStadiumOptionResponse] = []
    guided_fields: list[BalanceGuidedFieldResponse] = []
    auto_entries: list[BalanceEntryDraftResponse] = []
    extra_manual_entries: list[BalanceEntryDraftResponse] = []
    issues: list[BalanceIssueResponse] = []


# ---------- Transfer ----------
class TransferBase(BaseModel):
    season_id: UUID
    from_team_id: Optional[UUID] = None
    to_team_id: Optional[UUID] = None
    player_name: str
    fee: float = 0.0
    type: str = "cessione"
    transfer_date: Optional[date] = None
    notes: Optional[str] = None


class TransferCreate(TransferBase):
    pass


class TransferUpdate(BaseModel):
    from_team_id: Optional[UUID] = None
    to_team_id: Optional[UUID] = None
    player_name: Optional[str] = None
    fee: Optional[float] = None
    type: Optional[str] = None
    transfer_date: Optional[date] = None
    notes: Optional[str] = None


class TransferResponse(_ORM, TransferBase):
    id: UUID
    created_at: datetime


# ---------- Fine ----------
class FineBase(BaseModel):
    season_id: UUID
    team_id: UUID
    reason: str
    amount: float
    paid: bool = False
    fine_date: Optional[date] = None


class FineCreate(FineBase):
    pass


class FineUpdate(BaseModel):
    reason: Optional[str] = None
    amount: Optional[float] = None
    paid: Optional[bool] = None
    fine_date: Optional[date] = None


class FineResponse(_ORM, FineBase):
    id: UUID
    created_at: datetime


# ---------- Honor ----------
class HonorBase(BaseModel):
    season_id: UUID
    team_id: UUID
    trophy: str
    position: Optional[int] = None
    notes: Optional[str] = None


class HonorCreate(HonorBase):
    pass


class HonorResponse(_ORM, HonorBase):
    id: UUID


# ---------- News ----------
class NewsPostBase(BaseModel):
    title: str
    body_md: str
    author: Optional[str] = None
    pinned: bool = False


class NewsPostCreate(NewsPostBase):
    pass


class NewsPostUpdate(BaseModel):
    title: Optional[str] = None
    body_md: Optional[str] = None
    author: Optional[str] = None
    pinned: Optional[bool] = None


class NewsPostResponse(_ORM, NewsPostBase):
    id: UUID
    published_at: datetime


# ---------- League calendar ----------
class LeagueStandingRow(BaseModel):
    position: int
    team: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int
    total_points: float


class LeagueScheduleMatch(BaseModel):
    home_team: str
    home_score: float | None = None
    away_score: float | None = None
    away_team: str
    result: str | None = None


class LeagueScheduleRound(BaseModel):
    league_round: int
    serie_a_round: int | None = None
    matches: list[LeagueScheduleMatch] = []


class LeagueCalendarResponse(BaseModel):
    title: str
    source_url: str | None = None
    standings: list[LeagueStandingRow] = []
    rounds: list[LeagueScheduleRound] = []


# ---------- Poll ----------
class PollOptionCreate(BaseModel):
    label: str


class PollOptionResponse(_ORM):
    id: UUID
    label: str
    votes_count: int


class PollCreate(BaseModel):
    question: str
    options: list[PollOptionCreate] = Field(..., min_length=2)
    closes_at: Optional[datetime] = None


class PollResponse(_ORM):
    id: UUID
    question: str
    is_open: bool
    created_at: datetime
    closes_at: Optional[datetime]
    options: list[PollOptionResponse] = []


class PollVoteRequest(BaseModel):
    option_id: UUID


# ============================================================
# Players (Rose)
# ============================================================
ACQUISITION_TYPES = (
    "owned",
    "loan_dry",
    "loan_with_right",
    "loan_with_obligation",
    "sold_definitively",
)
FASCIA_VALUES = (
    "1_9",
    "10_19",
    "20_34",
    "35_49",
    "50_69",
    "70_89",
    "90_120",
    "120_plus",
)
LEGACY_FASCIA_VALUES = ("1_19", "20_59", "60_plus")


class PlayerBase(BaseModel):
    name: str = Field(..., max_length=160)
    role: str = Field(..., max_length=20)
    fascia: Literal[
        "1_9", "10_19", "20_34", "35_49", "50_69", "70_89", "90_120", "120_plus"
    ] = "1_9"
    salary: float = 0.0
    market_value: float = 0.0
    contract_years_total: int = 1
    contract_years_remaining: int = 1
    acquisition_type: Literal[
        "owned",
        "loan_dry",
        "loan_with_right",
        "loan_with_obligation",
        "sold_definitively",
    ] = "owned"
    acquisition_season_id: Optional[UUID] = None
    notes: Optional[str] = None
    is_active: bool = True


class PlayerCreate(PlayerBase):
    team_id: UUID
    season_id: UUID


class PlayerUpdate(BaseModel):
    team_id: Optional[UUID] = None
    season_id: Optional[UUID] = None
    name: Optional[str] = None
    role: Optional[str] = None
    fascia: Optional[
        Literal[
            "1_9", "10_19", "20_34", "35_49", "50_69", "70_89", "90_120", "120_plus"
        ]
    ] = None
    salary: Optional[float] = None
    market_value: Optional[float] = None
    contract_years_total: Optional[int] = None
    contract_years_remaining: Optional[int] = None
    acquisition_type: Optional[
        Literal[
            "owned",
            "loan_dry",
            "loan_with_right",
            "loan_with_obligation",
            "sold_definitively",
        ]
    ] = None
    acquisition_season_id: Optional[UUID] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PlayerResponse(_ORM, PlayerBase):
    fascia: Literal[
        "1_9",
        "10_19",
        "20_34",
        "35_49",
        "50_69",
        "70_89",
        "90_120",
        "120_plus",
        "1_19",
        "20_59",
        "60_plus",
    ]
    id: UUID
    team_id: UUID
    season_id: UUID
    created_at: datetime
    updated_at: datetime


class PlayerBulkCreate(BaseModel):
    players: list[PlayerCreate]


class RosterSummary(BaseModel):
    season_id: Optional[UUID] = None
    count: int = 0
    total_salary: float = 0.0
    total_value: float = 0.0
    by_fascia: dict[str, int] = Field(default_factory=dict)
    by_acquisition: dict[str, int] = Field(default_factory=dict)


# ============================================================
# Trade proposals (Mercato)
# ============================================================
PROPOSAL_KINDS = ("buy", "sell", "swap", "loan")
PROPOSAL_STATUSES = ("proposed", "accepted", "rejected", "cancelled", "ratified")
PROPOSAL_DIRECTIONS = ("from_proposer", "from_counterparty")


class TradeProposalItemCreate(BaseModel):
    player_id: UUID
    direction: Literal["from_proposer", "from_counterparty"]
    acquisition_type_after: Literal[
        "owned", "loan_dry", "loan_with_right", "loan_with_obligation"
    ] = "owned"
    contract_years_after: Optional[int] = None
    salary_after: Optional[float] = None
    market_value_after: Optional[float] = None


class TradeProposalCreate(BaseModel):
    season_id: UUID
    to_team_id: UUID
    kind: Literal["buy", "sell", "swap", "loan"] = "swap"
    cash_amount: float = 0.0
    notes: Optional[str] = None
    items: list[TradeProposalItemCreate] = Field(..., min_length=1)


class TradeProposalActionPayload(BaseModel):
    admin_notes: Optional[str] = None
    notes: Optional[str] = None


class TradeProposalItemResponse(_ORM):
    id: UUID
    proposal_id: UUID
    player_id: UUID
    direction: str
    acquisition_type_after: str
    contract_years_after: Optional[int] = None
    salary_after: Optional[float] = None
    market_value_after: Optional[float] = None
    # decorated by router for richer UI rendering
    player_name: Optional[str] = None
    player_role: Optional[str] = None


class TradeProposalResponse(_ORM):
    id: UUID
    season_id: UUID
    from_team_id: UUID
    to_team_id: UUID
    kind: str
    status: str
    cash_amount: float
    notes: Optional[str] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    ratified_at: Optional[datetime] = None
    items: list[TradeProposalItemResponse] = []
    from_team_name: Optional[str] = None
    to_team_name: Optional[str] = None


# ============================================================
# Cassa summary
# ============================================================
class FineSummaryRow(BaseModel):
    team_id: UUID
    team_name: str
    total: float = 0.0
    paid: float = 0.0
    unpaid: float = 0.0
    count: int = 0


class FineSummaryResponse(BaseModel):
    season_id: Optional[UUID] = None
    total: float = 0.0
    paid: float = 0.0
    unpaid: float = 0.0
    count: int = 0
    rows: list[FineSummaryRow] = []
    by_month: list[dict] = []


# ============================================================
# Balance draft/submit payloads
# ============================================================
class BalanceEntryDraft(BaseModel):
    id: Optional[UUID] = None
    section: Literal["ricavi", "costi", "ammortamenti", "plus_minus"]
    label: str
    amount: float = 0.0
    meta: Optional[dict] = None


class BalanceDraftUpdate(BaseModel):
    entries: list[BalanceEntryDraft]


# ============================================================
# Extended team dashboard with roster summary
# ============================================================
class TeamDashboardExtra(BaseModel):
    roster_summary: Optional[RosterSummary] = None
    pending_incoming_trades: int = 0
    pending_outgoing_trades: int = 0
