"""Read-only & admin endpoints for the Fantacalcio league."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.core.auth import get_current_team, optional_admin, optional_team, require_admin
from app.core.security import create_access_token, get_password_hash, verify_password
from app.database import get_db
from app.models.league import (
    BalanceEntry,
    BalanceSheet,
    Fine,
    Honor,
    NewsPost,
    Player,
    Poll,
    PollOption,
    PollVote,
    Season,
    Team,
    TradeProposal,
    Transfer,
)
from app.schemas.league import (
    BalanceDraftUpdate,
    BalanceGuidedResponse,
    BalanceSheetResponse,
    FineCreate,
    FineResponse,
    FineSummaryResponse,
    FineSummaryRow,
    FineUpdate,
    HonorCreate,
    HonorResponse,
    LeagueCalendarResponse,
    NewsPostCreate,
    NewsPostResponse,
    NewsPostUpdate,
    PollCreate,
    PollResponse,
    PollVoteRequest,
    RosterSummary,
    SeasonCreate,
    SeasonResponse,
    SeasonUpdate,
    TeamAccountResponse,
    TeamAdminStatusResponse,
    TeamCreate,
    TeamDashboardResponse,
    TeamLoginRequest,
    TeamLoginResponse,
    TeamResponse,
    TeamSelfUpdate,
    TeamUpdate,
    TransferCreate,
    TransferResponse,
    TransferUpdate,
)
from app.services.balance_calc_service import (
    get_or_create_draft,
    recompute_totals,
    replace_entries,
)
from app.services.balance_guided_service import (
    build_admin_balance_issues,
    build_guided_payload,
    normalize_guided_entries,
    sync_balance_draft,
)
from app.services.league_calendar_service import (
    get_league_calendar_data_from_db,
    parse_calendar_excel,
    parse_rose_excel,
    parse_standings_excel,
)
from app.services.balance_service import BalanceImportService, SanctionService
from app.services.trade_service import is_auto_market_transfer

router = APIRouter(tags=["League"])

AdminDep = Depends(require_admin)
TeamDep = Depends(get_current_team)

UPLOADABLE_LEAGUE_KINDS = {"rose", "calendar", "classifica"}

calendar_router = APIRouter(prefix="/calendar", tags=["Calendar"])


@calendar_router.get("/", response_model=LeagueCalendarResponse)
def get_league_calendar(db: Session = Depends(get_db)):
    data = get_league_calendar_data_from_db(db)
    return LeagueCalendarResponse.model_validate(asdict(data))


def _slugify_username(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "squadra"


def _build_unique_username(
    db: Session, raw_value: str, exclude_team_id: UUID | None = None
) -> str:
    base = _slugify_username(raw_value)
    candidate = base
    suffix = 1
    while True:
        stmt = select(Team).where(Team.account_username == candidate)
        existing = db.execute(stmt).scalar_one_or_none()
        if not existing or existing.id == exclude_team_id:
            return candidate
        suffix += 1
        candidate = f"{base}_{suffix}"


def _serialize_team_account(team: Team) -> TeamAccountResponse:
    return TeamAccountResponse.model_validate(team)


def _resolve_current_season(db: Session) -> Season | None:
    return (
        db.execute(
            select(Season).order_by(Season.is_current.desc(), Season.name.desc())
        )
        .scalars()
        .first()
    )


def _import_standings_to_db(db: Session, content: bytes) -> int:
    from app.models.league import Season, StandingRow as StandingRowModel
    from sqlalchemy import delete as sa_delete

    current_season = db.execute(
        select(Season).where(Season.is_current.is_(True))
    ).scalar_one_or_none()
    if not current_season:
        raise HTTPException(400, "Nessuna stagione corrente impostata")

    rows = parse_standings_excel(content)
    if not rows:
        raise HTTPException(400, "Nessuna riga trovata nel file classifica")

    db.execute(
        sa_delete(StandingRowModel).where(
            StandingRowModel.season_id == current_season.id
        )
    )
    for r in rows:
        db.add(StandingRowModel(season_id=current_season.id, **r))
    db.commit()
    return len(rows)


def _import_calendar_to_db(db: Session, content: bytes) -> int:
    from app.models.league import CalendarRound, CalendarMatch, Season
    from sqlalchemy import delete as sa_delete

    current_season = db.execute(
        select(Season).where(Season.is_current.is_(True))
    ).scalar_one_or_none()
    if not current_season:
        raise HTTPException(400, "Nessuna stagione corrente impostata")

    rounds_data = parse_calendar_excel(content)
    if not rounds_data:
        raise HTTPException(400, "Nessun girone trovato nel file calendario")

    db.execute(
        sa_delete(CalendarRound).where(CalendarRound.season_id == current_season.id)
    )
    for rnd in rounds_data:
        db_round = CalendarRound(
            season_id=current_season.id,
            league_round=rnd["league_round"],
            serie_a_round=rnd["serie_a_round"],
        )
        db.add(db_round)
        db.flush()
        for m in rnd["matches"]:
            db.add(CalendarMatch(round_id=db_round.id, **m))
    db.commit()
    return len(rounds_data)


def _import_rose_to_db(db: Session, content: bytes) -> int:
    from app.models.league import Player, Season, Team
    from sqlalchemy import delete as sa_delete

    current_season = db.execute(
        select(Season).where(Season.is_current.is_(True))
    ).scalar_one_or_none()
    if not current_season:
        raise HTTPException(400, "Nessuna stagione corrente impostata")

    teams_data = parse_rose_excel(content)
    if not teams_data:
        raise HTTPException(400, "Nessuna squadra trovata nel file rose")

    imported = 0
    for team_data in teams_data:
        team = db.execute(
            select(Team).where(Team.name == team_data["team_name"])
        ).scalar_one_or_none()
        if not team:
            slug = _slugify_username(team_data["team_name"])
            # Ensure username uniqueness
            base_slug = slug
            counter = 1
            while db.execute(
                select(Team).where(Team.account_username == slug)
            ).scalar_one_or_none():
                slug = f"{base_slug}_{counter}"
                counter += 1
            team = Team(
                name=team_data["team_name"],
                account_username=slug,
                password_hash=get_password_hash("utente"),
                is_active=True,
            )
            db.add(team)
            db.flush()
        db.execute(
            sa_delete(Player).where(
                Player.team_id == team.id,
                Player.season_id == current_season.id,
            )
        )
        for p in team_data["players"]:
            db.add(Player(team_id=team.id, season_id=current_season.id, **p))
            imported += 1
    db.commit()
    return imported


def _load_balance_with_entries(db: Session, stmt):
    return db.execute(
        stmt.options(selectinload(BalanceSheet.entries))
    ).scalar_one_or_none()


def _save_balance_import(
    *,
    db: Session,
    team_id: UUID,
    season_id: UUID,
    filename: str,
    content: bytes,
) -> BalanceSheet:
    parsed = BalanceImportService.parse(content, filename)
    sanction = SanctionService.evaluate(parsed.utile)

    uploads = Path(settings.uploads_dir) / "balances"
    uploads.mkdir(parents=True, exist_ok=True)
    safe_name = f"{team_id}_{season_id}_{filename or 'bilancio.xlsx'}"
    filepath = uploads / safe_name
    filepath.write_bytes(content)

    existing = db.execute(
        select(BalanceSheet).where(
            BalanceSheet.team_id == team_id, BalanceSheet.season_id == season_id
        )
    ).scalar_one_or_none()
    if existing:
        db.delete(existing)
        db.flush()

    sheet = BalanceSheet(
        team_id=team_id,
        season_id=season_id,
        status="submitted",
        file_url=f"/{filepath.as_posix()}",
        total_ricavi=parsed.total_ricavi,
        total_costi=parsed.total_costi,
        total_ammortamenti=parsed.total_ammortamenti,
        total_plus_minus=parsed.total_plus_minus,
        utile=parsed.utile,
        sanction_level=sanction.level,
        sanction_points=sanction.points,
        sanction_notes=sanction.notes,
    )
    db.add(sheet)
    db.flush()

    for entry in parsed.entries:
        db.add(
            BalanceEntry(
                balance_sheet_id=sheet.id,
                section=entry.section,
                label=entry.label,
                amount=entry.amount,
                meta=entry.meta,
            )
        )
    db.commit()

    stmt = select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    return db.execute(stmt.options(selectinload(BalanceSheet.entries))).scalar_one()


def _build_team_dashboard(team: Team, db: Session) -> TeamDashboardResponse:
    current_season = _resolve_current_season(db)
    latest_balance = (
        db.execute(
            select(BalanceSheet)
            .options(selectinload(BalanceSheet.entries))
            .where(BalanceSheet.team_id == team.id)
            .order_by(BalanceSheet.submitted_at.desc())
        )
        .scalars()
        .first()
    )
    recent_balances = (
        db.execute(
            select(BalanceSheet)
            .options(selectinload(BalanceSheet.entries))
            .where(BalanceSheet.team_id == team.id)
            .order_by(BalanceSheet.submitted_at.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )
    fines = (
        db.execute(
            select(Fine).where(Fine.team_id == team.id).order_by(Fine.created_at.desc())
        )
        .scalars()
        .all()
    )
    transfers = (
        db.execute(
            select(Transfer)
            .where(
                (Transfer.from_team_id == team.id) | (Transfer.to_team_id == team.id)
            )
            .order_by(
                Transfer.transfer_date.desc().nulls_last(), Transfer.created_at.desc()
            )
            .limit(10)
        )
        .scalars()
        .all()
    )
    honors = db.execute(select(Honor).where(Honor.team_id == team.id)).scalars().all()
    unpaid_fines_total = sum(f.amount for f in fines if not f.paid)

    current_balance = None
    if current_season:
        current_balance = next(
            (b for b in recent_balances if b.season_id == current_season.id), None
        )
    has_uploaded_current_balance = bool(
        current_balance and current_balance.status == "submitted"
    )
    current_balance_status = current_balance.status if current_balance else None

    roster: list[Player] = []
    if current_season:
        roster = (
            db.execute(
                select(Player).where(
                    Player.team_id == team.id,
                    Player.season_id == current_season.id,
                    Player.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
    by_fascia: dict[str, int] = {}
    by_acquisition: dict[str, int] = {}
    total_salary = 0.0
    total_value = 0.0
    for p in roster:
        by_fascia[p.fascia] = by_fascia.get(p.fascia, 0) + 1
        by_acquisition[p.acquisition_type] = (
            by_acquisition.get(p.acquisition_type, 0) + 1
        )
        total_salary += float(p.salary or 0.0)
        total_value += float(p.market_value or 0.0)
    roster_summary = RosterSummary(
        season_id=current_season.id if current_season else None,
        count=len(roster),
        total_salary=total_salary,
        total_value=total_value,
        by_fascia=by_fascia,
        by_acquisition=by_acquisition,
    )

    pending_incoming = (
        db.execute(
            select(TradeProposal).where(
                TradeProposal.to_team_id == team.id, TradeProposal.status == "proposed"
            )
        )
        .scalars()
        .all()
    )
    pending_outgoing = (
        db.execute(
            select(TradeProposal).where(
                TradeProposal.from_team_id == team.id,
                TradeProposal.status.in_(("proposed", "accepted")),
            )
        )
        .scalars()
        .all()
    )

    return TeamDashboardResponse(
        team=_serialize_team_account(team),
        current_season=(
            SeasonResponse.model_validate(current_season) if current_season else None
        ),
        latest_balance=(
            BalanceSheetResponse.model_validate(latest_balance)
            if latest_balance
            else None
        ),
        recent_balances=[
            BalanceSheetResponse.model_validate(balance) for balance in recent_balances
        ],
        fines=[FineResponse.model_validate(fine) for fine in fines],
        transfers=[TransferResponse.model_validate(transfer) for transfer in transfers],
        honors=[HonorResponse.model_validate(honor) for honor in honors],
        unpaid_fines_total=unpaid_fines_total,
        has_uploaded_current_balance=has_uploaded_current_balance,
        current_balance_status=current_balance_status,
        roster_summary=roster_summary,
        pending_incoming_trades=len(pending_incoming),
        pending_outgoing_trades=len(pending_outgoing),
    )


# ============================================================
# Seasons
# ============================================================
seasons_router = APIRouter(prefix="/seasons", tags=["Seasons"])


@seasons_router.get("/", response_model=list[SeasonResponse])
def list_seasons(db: Session = Depends(get_db)):
    return db.execute(select(Season).order_by(Season.name.desc())).scalars().all()


@seasons_router.post(
    "/", response_model=SeasonResponse, status_code=201, dependencies=[AdminDep]
)
def create_season(payload: SeasonCreate, db: Session = Depends(get_db)):
    if payload.is_current:
        for s in db.execute(select(Season)).scalars().all():
            s.is_current = False
    obj = Season(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@seasons_router.put(
    "/{season_id}", response_model=SeasonResponse, dependencies=[AdminDep]
)
def update_season(
    season_id: UUID, payload: SeasonUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Season, season_id)
    if not obj:
        raise HTTPException(404)
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_current"):
        for s in db.execute(select(Season)).scalars().all():
            s.is_current = False
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@seasons_router.delete("/{season_id}", status_code=204, dependencies=[AdminDep])
def delete_season(season_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Season, season_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# Teams
# ============================================================
teams_router = APIRouter(prefix="/teams", tags=["Teams"])


@teams_router.get("/", response_model=list[TeamAccountResponse])
def list_teams(db: Session = Depends(get_db)):
    return db.execute(select(Team).order_by(Team.name)).scalars().all()


@teams_router.post(
    "/", response_model=TeamResponse, status_code=201, dependencies=[AdminDep]
)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    username = _build_unique_username(db, payload.account_username or payload.name)
    obj = Team(
        name=payload.name,
        account_username=username,
        password_hash=get_password_hash(payload.password or "utente"),
        manager_name=payload.manager_name,
        logo_url=payload.logo_url,
        founded_year=payload.founded_year,
        profile_bio=payload.profile_bio,
        home_city=payload.home_city,
        is_active=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@teams_router.put("/{team_id}", response_model=TeamResponse, dependencies=[AdminDep])
def update_team(team_id: UUID, payload: TeamUpdate, db: Session = Depends(get_db)):
    obj = db.get(Team, team_id)
    if not obj:
        raise HTTPException(404)
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    account_username = data.pop("account_username", None)
    for k, v in data.items():
        setattr(obj, k, v)
    if account_username:
        obj.account_username = _build_unique_username(db, account_username, obj.id)
    if password:
        obj.password_hash = get_password_hash(password)
    db.commit()
    db.refresh(obj)
    return obj


@teams_router.delete("/{team_id}", status_code=204, dependencies=[AdminDep])
def delete_team(team_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Team, team_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# Balances
# ============================================================
balances_router = APIRouter(prefix="/balances", tags=["Balances"])


@balances_router.get("/", response_model=list[BalanceSheetResponse])
def list_balances(
    season_id: UUID | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access balances",
        )

    stmt = select(BalanceSheet).options(selectinload(BalanceSheet.entries))

    if current_team and not is_admin:
        stmt = stmt.where(BalanceSheet.team_id == current_team.id)

    if season_id:
        stmt = stmt.where(BalanceSheet.season_id == season_id)
    if team_id:
        if current_team and not is_admin and team_id != current_team.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own team's balances",
            )
        stmt = stmt.where(BalanceSheet.team_id == team_id)
    return db.execute(stmt.order_by(BalanceSheet.submitted_at.desc())).scalars().all()


@balances_router.get("/{balance_id}", response_model=BalanceSheetResponse)
def get_balance(
    balance_id: UUID,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    stmt = (
        select(BalanceSheet)
        .options(selectinload(BalanceSheet.entries))
        .where(BalanceSheet.id == balance_id)
    )
    obj = db.execute(stmt).scalar_one_or_none()
    if not obj:
        raise HTTPException(404)

    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access balances",
        )

    if current_team and not is_admin and obj.team_id != current_team.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own team's balances",
        )

    return obj


@balances_router.get("/template/excel")
def download_template():
    data = BalanceImportService.build_template_xlsx()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="bilancio_template.xlsx"'
        },
    )


@balances_router.post("/my/import", response_model=BalanceSheetResponse)
async def import_my_balance(
    season_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    team: Team = TeamDep,
    db: Session = Depends(get_db),
):
    if not db.get(Season, season_id):
        raise HTTPException(404, "Season not found")
    content = await file.read()
    return _save_balance_import(
        db=db,
        team_id=team.id,
        season_id=season_id,
        filename=file.filename or "bilancio.xlsx",
        content=content,
    )


@balances_router.post(
    "/import", response_model=BalanceSheetResponse, dependencies=[AdminDep]
)
async def import_balance(
    team_id: Annotated[UUID, Form()],
    season_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
):
    if not db.get(Team, team_id):
        raise HTTPException(404, "Team not found")
    if not db.get(Season, season_id):
        raise HTTPException(404, "Season not found")

    content = await file.read()
    return _save_balance_import(
        db=db,
        team_id=team_id,
        season_id=season_id,
        filename=file.filename or "bilancio.xlsx",
        content=content,
    )


@balances_router.delete("/{balance_id}", status_code=204, dependencies=[AdminDep])
def delete_balance(balance_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(BalanceSheet, balance_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ---- On-site form: draft / submit / reopen ----


@balances_router.get("/my/current", response_model=BalanceSheetResponse)
def get_my_current_balance(
    season_id: UUID | None = None,
    team: Team = TeamDep,
    db: Session = Depends(get_db),
):
    if season_id is None:
        current = _resolve_current_season(db)
        if not current:
            raise HTTPException(404, "No season available")
        season_id = current.id
    if not db.get(Season, season_id):
        raise HTTPException(404, "Season not found")
    sheet = get_or_create_draft(db, team_id=team.id, season_id=season_id)
    if sheet.status == "draft":
        sync_balance_draft(db, sheet)
        db.commit()
    return _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )


@balances_router.get("/my/current/guided", response_model=BalanceGuidedResponse)
def get_my_current_guided_balance(
    season_id: UUID | None = None,
    team: Team = TeamDep,
    db: Session = Depends(get_db),
):
    if season_id is None:
        current = _resolve_current_season(db)
        if not current:
            raise HTTPException(404, "No season available")
        season_id = current.id
    if not db.get(Season, season_id):
        raise HTTPException(404, "Season not found")
    sheet = get_or_create_draft(db, team_id=team.id, season_id=season_id)
    payload = build_guided_payload(db, sheet)
    db.commit()
    sheet = _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )
    return BalanceGuidedResponse.model_validate({"balance": sheet, **payload})


@balances_router.get(
    "/{balance_id}/guided",
    response_model=BalanceGuidedResponse,
    dependencies=[AdminDep],
)
def get_admin_guided_balance(balance_id: UUID, db: Session = Depends(get_db)):
    sheet = db.get(BalanceSheet, balance_id)
    if not sheet:
        raise HTTPException(404)
    payload = build_guided_payload(db, sheet)
    db.commit()
    sheet = _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )
    return BalanceGuidedResponse.model_validate({"balance": sheet, **payload})


@balances_router.put("/{balance_id}/draft", response_model=BalanceSheetResponse)
def update_balance_draft(
    balance_id: UUID,
    payload: BalanceDraftUpdate,
    team: Team = TeamDep,
    db: Session = Depends(get_db),
):
    sheet = db.get(BalanceSheet, balance_id)
    if not sheet:
        raise HTTPException(404)
    if sheet.team_id != team.id:
        raise HTTPException(403, "Not your balance")
    if sheet.status != "draft":
        raise HTTPException(409, "Balance already submitted; ask admin to reopen")
    normalized_entries = normalize_guided_entries(
        db, sheet, [e.model_dump() for e in payload.entries]
    )
    replace_entries(db, sheet, normalized_entries)
    recompute_totals(sheet)
    db.commit()
    return _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )


@balances_router.put(
    "/{balance_id}/admin/draft",
    response_model=BalanceSheetResponse,
    dependencies=[AdminDep],
)
def admin_update_balance_draft(
    balance_id: UUID,
    payload: BalanceDraftUpdate,
    db: Session = Depends(get_db),
):
    sheet = db.get(BalanceSheet, balance_id)
    if not sheet:
        raise HTTPException(404)
    normalized_entries = normalize_guided_entries(
        db, sheet, [e.model_dump() for e in payload.entries]
    )
    replace_entries(db, sheet, normalized_entries)
    recompute_totals(sheet)
    db.commit()
    return _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )


@balances_router.post("/{balance_id}/submit", response_model=BalanceSheetResponse)
def submit_balance(
    balance_id: UUID,
    team: Team = TeamDep,
    db: Session = Depends(get_db),
):
    sheet = db.get(BalanceSheet, balance_id)
    if not sheet:
        raise HTTPException(404)
    if sheet.team_id != team.id:
        raise HTTPException(403, "Not your balance")
    if sheet.status != "draft":
        raise HTTPException(409, "Balance is not in draft")
    recompute_totals(sheet)
    sheet.status = "submitted"
    sheet.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )


@balances_router.post(
    "/{balance_id}/reopen",
    response_model=BalanceSheetResponse,
    dependencies=[AdminDep],
)
def reopen_balance(balance_id: UUID, db: Session = Depends(get_db)):
    sheet = db.get(BalanceSheet, balance_id)
    if not sheet:
        raise HTTPException(404)
    sheet.status = "draft"
    db.commit()
    return _load_balance_with_entries(
        db, select(BalanceSheet).where(BalanceSheet.id == sheet.id)
    )


# ============================================================
# Transfers
# ============================================================
transfers_router = APIRouter(prefix="/transfers", tags=["Transfers"])


@transfers_router.get("/", response_model=list[TransferResponse])
def list_transfers(season_id: UUID | None = None, db: Session = Depends(get_db)):
    stmt = select(Transfer)
    if season_id:
        stmt = stmt.where(Transfer.season_id == season_id)
    transfers = (
        db.execute(stmt.order_by(Transfer.transfer_date.desc().nulls_last()))
        .scalars()
        .all()
    )
    return [
        transfer for transfer in transfers if not is_auto_market_transfer(transfer.type)
    ]


@transfers_router.post(
    "/", response_model=TransferResponse, status_code=201, dependencies=[AdminDep]
)
def create_transfer(payload: TransferCreate, db: Session = Depends(get_db)):
    obj = Transfer(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@transfers_router.put(
    "/{transfer_id}", response_model=TransferResponse, dependencies=[AdminDep]
)
def update_transfer(
    transfer_id: UUID, payload: TransferUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Transfer, transfer_id)
    if not obj:
        raise HTTPException(404)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@transfers_router.delete("/{transfer_id}", status_code=204, dependencies=[AdminDep])
def delete_transfer(transfer_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Transfer, transfer_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# Fines
# ============================================================
fines_router = APIRouter(prefix="/fines", tags=["Fines"])


@fines_router.get("/", response_model=list[FineResponse], dependencies=[AdminDep])
def list_fines(
    season_id: UUID | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Fine)
    if season_id:
        stmt = stmt.where(Fine.season_id == season_id)
    if team_id:
        stmt = stmt.where(Fine.team_id == team_id)
    return db.execute(stmt.order_by(Fine.created_at.desc())).scalars().all()


@fines_router.get(
    "/summary",
    response_model=FineSummaryResponse,
    dependencies=[AdminDep],
)
def fines_summary(
    season_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Fine)
    if season_id:
        stmt = stmt.where(Fine.season_id == season_id)
    fines = db.execute(stmt).scalars().all()
    teams = {t.id: t for t in db.execute(select(Team)).scalars().all()}
    rows: dict[UUID, FineSummaryRow] = {}
    by_month: dict[str, dict] = {}
    total = paid = unpaid = 0.0
    for f in fines:
        team = teams.get(f.team_id)
        if not team:
            continue
        row = rows.get(team.id)
        if not row:
            row = FineSummaryRow(team_id=team.id, team_name=team.name)
            rows[team.id] = row
        amount = float(f.amount or 0.0)
        row.count += 1
        row.total += amount
        total += amount
        if f.paid:
            row.paid += amount
            paid += amount
        else:
            row.unpaid += amount
            unpaid += amount
        ref_date = f.fine_date or f.created_at.date()
        if ref_date is not None:
            key = ref_date.strftime("%Y-%m")
            bm = by_month.setdefault(key, {"month": key, "total": 0.0, "count": 0})
            bm["total"] += amount
            bm["count"] += 1
    return FineSummaryResponse(
        season_id=season_id,
        total=total,
        paid=paid,
        unpaid=unpaid,
        count=len(fines),
        rows=sorted(rows.values(), key=lambda r: r.team_name),
        by_month=sorted(by_month.values(), key=lambda r: r["month"]),
    )


@fines_router.post(
    "/", response_model=FineResponse, status_code=201, dependencies=[AdminDep]
)
def create_fine(payload: FineCreate, db: Session = Depends(get_db)):
    obj = Fine(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@fines_router.put("/{fine_id}", response_model=FineResponse, dependencies=[AdminDep])
def update_fine(fine_id: UUID, payload: FineUpdate, db: Session = Depends(get_db)):
    obj = db.get(Fine, fine_id)
    if not obj:
        raise HTTPException(404)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@fines_router.delete("/{fine_id}", status_code=204, dependencies=[AdminDep])
def delete_fine(fine_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Fine, fine_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# Honors (Albo d'oro)
# ============================================================
honors_router = APIRouter(prefix="/honors", tags=["Honors"])


@honors_router.get("/", response_model=list[HonorResponse])
def list_honors(season_id: UUID | None = None, db: Session = Depends(get_db)):
    stmt = select(Honor)
    if season_id:
        stmt = stmt.where(Honor.season_id == season_id)
    return db.execute(stmt).scalars().all()


@honors_router.post(
    "/", response_model=HonorResponse, status_code=201, dependencies=[AdminDep]
)
def create_honor(payload: HonorCreate, db: Session = Depends(get_db)):
    obj = Honor(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@honors_router.delete("/{honor_id}", status_code=204, dependencies=[AdminDep])
def delete_honor(honor_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Honor, honor_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# News
# ============================================================
news_router = APIRouter(prefix="/news", tags=["News"])


@news_router.get("/", response_model=list[NewsPostResponse])
def list_news(limit: int = 50, db: Session = Depends(get_db)):
    stmt = (
        select(NewsPost)
        .order_by(NewsPost.pinned.desc(), NewsPost.published_at.desc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


@news_router.post("/", response_model=NewsPostResponse, status_code=201)
def create_news(
    payload: NewsPostCreate,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to publish a message",
        )

    data = payload.model_dump()
    if current_team and not is_admin:
        data["author"] = current_team.name
        data["pinned"] = False

    obj = NewsPost(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@news_router.put("/{post_id}", response_model=NewsPostResponse, dependencies=[AdminDep])
def update_news(post_id: UUID, payload: NewsPostUpdate, db: Session = Depends(get_db)):
    obj = db.get(NewsPost, post_id)
    if not obj:
        raise HTTPException(404)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@news_router.delete("/{post_id}", status_code=204, dependencies=[AdminDep])
def delete_news(post_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(NewsPost, post_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# Polls
# ============================================================
polls_router = APIRouter(prefix="/polls", tags=["Polls"])


@polls_router.get("/", response_model=list[PollResponse])
def list_polls(db: Session = Depends(get_db)):
    stmt = (
        select(Poll)
        .options(selectinload(Poll.options))
        .order_by(Poll.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@polls_router.post(
    "/", response_model=PollResponse, status_code=201, dependencies=[AdminDep]
)
def create_poll(payload: PollCreate, db: Session = Depends(get_db)):
    poll = Poll(question=payload.question, closes_at=payload.closes_at)
    db.add(poll)
    db.flush()
    for opt in payload.options:
        db.add(PollOption(poll_id=poll.id, label=opt.label))
    db.commit()
    stmt = select(Poll).options(selectinload(Poll.options)).where(Poll.id == poll.id)
    return db.execute(stmt).scalar_one()


@polls_router.post("/{poll_id}/vote", response_model=PollResponse)
def vote(
    poll_id: UUID,
    payload: PollVoteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    poll = db.get(Poll, poll_id)
    if not poll or not poll.is_open:
        raise HTTPException(400, "Sondaggio non disponibile")
    option = db.get(PollOption, payload.option_id)
    if not option or option.poll_id != poll_id:
        raise HTTPException(404, "Opzione non valida")

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    voter_hash = hashlib.sha256(f"{ip}|{ua}|{poll_id}".encode()).hexdigest()

    existing = db.execute(
        select(PollVote).where(
            PollVote.poll_id == poll_id, PollVote.voter_hash == voter_hash
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Hai gia' votato in questo sondaggio")

    db.add(PollVote(poll_id=poll_id, option_id=option.id, voter_hash=voter_hash))
    option.votes_count = (option.votes_count or 0) + 1
    db.commit()

    stmt = select(Poll).options(selectinload(Poll.options)).where(Poll.id == poll_id)
    return db.execute(stmt).scalar_one()


@polls_router.delete("/{poll_id}", status_code=204, dependencies=[AdminDep])
def delete_poll(poll_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Poll, poll_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


# ============================================================
# Rules / Guida (markdown content from disk)
# ============================================================
rules_router = APIRouter(prefix="/content", tags=["Content"])

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


@rules_router.get("/{slug}")
def get_content(slug: str):
    if not slug.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "Invalid slug")
    fp = CONTENT_DIR / f"{slug}.md"
    if not fp.exists():
        raise HTTPException(404)
    return {"slug": slug, "body_md": fp.read_text(encoding="utf-8")}


# ============================================================
# Admin verify
# ============================================================
@router.post("/admin/verify", dependencies=[AdminDep])
def verify_admin():
    return {"ok": True}


@router.post("/admin/uploads/{kind}", dependencies=[AdminDep])
def upload_league_asset(
    kind: str, file: Annotated[UploadFile, File()], db: Session = Depends(get_db)
):
    if kind not in UPLOADABLE_LEAGUE_KINDS:
        raise HTTPException(400, "Tipo file non supportato")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".xlsx", ".xls"}:
        raise HTTPException(400, "Carica un file Excel .xlsx o .xls")

    content = file.file.read()
    if not content:
        raise HTTPException(400, "File vuoto")

    if kind == "classifica":
        count = _import_standings_to_db(db, content)
        return {"ok": True, "kind": kind, "imported": count}
    elif kind == "calendar":
        count = _import_calendar_to_db(db, content)
        return {"ok": True, "kind": kind, "imported": count}
    elif kind == "rose":
        count = _import_rose_to_db(db, content)
        return {"ok": True, "kind": kind, "imported": count}


@router.post("/team-auth/login", response_model=TeamLoginResponse)
def login_team(payload: TeamLoginRequest, db: Session = Depends(get_db)):
    team = db.execute(
        select(Team).where(Team.account_username == payload.username.strip().lower())
    ).scalar_one_or_none()
    if not team or not verify_password(payload.password, team.password_hash):
        raise HTTPException(status_code=401, detail="Credenziali squadra non valide")
    if not team.is_active:
        raise HTTPException(status_code=403, detail="Profilo squadra disattivato")

    team.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(team)
    return TeamLoginResponse(
        access_token=create_access_token(str(team.id), token_type="team"),
        team=_serialize_team_account(team),
    )


@router.get("/team-auth/me", response_model=TeamAccountResponse)
def get_team_me(team: Team = TeamDep):
    return _serialize_team_account(team)


@router.put("/team-auth/me", response_model=TeamAccountResponse)
def update_team_me(
    payload: TeamSelfUpdate,
    team: Team = TeamDep,
    db: Session = Depends(get_db),
):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, key, value)
    db.commit()
    db.refresh(team)
    return _serialize_team_account(team)


@router.get("/team-auth/dashboard", response_model=TeamDashboardResponse)
def get_team_dashboard(team: Team = TeamDep, db: Session = Depends(get_db)):
    return _build_team_dashboard(team, db)


@router.get(
    "/admin/teams/status",
    response_model=list[TeamAdminStatusResponse],
    dependencies=[AdminDep],
)
def get_admin_team_status(db: Session = Depends(get_db)):
    current_season = _resolve_current_season(db)
    teams = db.execute(select(Team).order_by(Team.name)).scalars().all()
    rows: list[TeamAdminStatusResponse] = []
    for team in teams:
        current_balance = None
        if current_season:
            current_balance = (
                db.execute(
                    select(BalanceSheet)
                    .options(selectinload(BalanceSheet.entries))
                    .where(
                        BalanceSheet.team_id == team.id,
                        BalanceSheet.season_id == current_season.id,
                    )
                    .order_by(BalanceSheet.submitted_at.desc())
                )
                .scalars()
                .first()
            )
        latest_balance = (
            current_balance
            or db.execute(
                select(BalanceSheet)
                .options(selectinload(BalanceSheet.entries))
                .where(BalanceSheet.team_id == team.id)
                .order_by(BalanceSheet.submitted_at.desc())
            )
            .scalars()
            .first()
        )
        unpaid_fines_total = sum(
            fine.amount
            for fine in db.execute(select(Fine).where(Fine.team_id == team.id))
            .scalars()
            .all()
            if not fine.paid
        )
        roster_count = 0
        if current_season:
            roster_count = len(
                db.execute(
                    select(Player).where(
                        Player.team_id == team.id,
                        Player.season_id == current_season.id,
                        Player.is_active.is_(True),
                    )
                )
                .scalars()
                .all()
            )
        profile_complete = bool(team.manager_name and team.profile_bio)
        has_uploaded_current_balance = bool(
            current_balance and current_balance.status == "submitted"
        )
        current_balance_status = current_balance.status if current_balance else None
        is_ok = (
            team.is_active and has_uploaded_current_balance and unpaid_fines_total <= 0
        )
        anomalies = (
            build_admin_balance_issues(
                db=db,
                team_id=team.id,
                season_id=current_season.id,
                balance=current_balance,
            )
            if current_season
            else []
        )
        is_ok = is_ok and len(anomalies) == 0
        rows.append(
            TeamAdminStatusResponse(
                team_id=team.id,
                team_name=team.name,
                account_username=team.account_username,
                manager_name=team.manager_name,
                current_season_name=current_season.name if current_season else None,
                profile_complete=profile_complete,
                has_uploaded_current_balance=has_uploaded_current_balance,
                current_balance_status=current_balance_status,
                latest_submitted_at=(
                    latest_balance.submitted_at if latest_balance else None
                ),
                latest_sanction_level=(
                    latest_balance.sanction_level if latest_balance else None
                ),
                latest_sanction_points=(
                    latest_balance.sanction_points if latest_balance else None
                ),
                unpaid_fines_total=unpaid_fines_total,
                roster_count=roster_count,
                anomalies=anomalies,
                is_ok=is_ok,
            )
        )
    return rows


# Aggregate
def include_all(parent: APIRouter):
    from app.api.v1.players import players_router
    from app.api.v1.trades import trades_router

    parent.include_router(router)
    parent.include_router(calendar_router)
    parent.include_router(seasons_router)
    parent.include_router(teams_router)
    parent.include_router(balances_router)
    parent.include_router(transfers_router)
    parent.include_router(fines_router)
    parent.include_router(honors_router)
    parent.include_router(news_router)
    parent.include_router(polls_router)
    parent.include_router(rules_router)
    parent.include_router(players_router)
    parent.include_router(trades_router)
