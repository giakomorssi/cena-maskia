"""Players (Rose) router. Read: any authenticated team or admin. Write: admin only."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import optional_admin, optional_team, require_admin
from app.database import get_db
from app.models.league import Player, Season, Team
from app.schemas.league import (
    PlayerBulkCreate,
    PlayerCreate,
    PlayerResponse,
    PlayerUpdate,
)
from app.services.player_finance_rules import normalize_player_financials

players_router = APIRouter(prefix="/players", tags=["Players"])

AdminDep = Depends(require_admin)


def _normalize_contract_duration(
    data: dict, *, fallback_total: int = 1, fallback_remaining: int = 1
) -> dict:
    normalized = dict(data)
    total = normalized.get("contract_years_total", fallback_total)
    remaining = normalized.get("contract_years_remaining", fallback_remaining)
    try:
        total_value = max(1, min(int(total or 1), 5))
    except (TypeError, ValueError):
        total_value = max(1, min(int(fallback_total or 1), 5))
    try:
        remaining_value = int(remaining or total_value)
    except (TypeError, ValueError):
        remaining_value = total_value
    normalized["contract_years_total"] = total_value
    normalized["contract_years_remaining"] = max(1, min(remaining_value, total_value))
    return normalized


def _ensure_read_access(
    *, is_admin: bool, current_team: Team | None, target_team_id: UUID
) -> None:
    if is_admin:
        return
    if not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access roster data",
        )
    return


@players_router.get("/", response_model=list[PlayerResponse])
def list_players(
    team_id: Optional[UUID] = None,
    season_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access roster data",
        )

    stmt = select(Player)
    if team_id:
        stmt = stmt.where(Player.team_id == team_id)
    if season_id:
        stmt = stmt.where(Player.season_id == season_id)
    return db.execute(stmt.order_by(Player.role, Player.name)).scalars().all()


@players_router.get("/{player_id}", response_model=PlayerResponse)
def get_player(
    player_id: UUID,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    obj = db.get(Player, player_id)
    if not obj:
        raise HTTPException(404)
    _ensure_read_access(
        is_admin=is_admin, current_team=current_team, target_team_id=obj.team_id
    )
    return obj


@players_router.post(
    "/", response_model=PlayerResponse, status_code=201, dependencies=[AdminDep]
)
def create_player(payload: PlayerCreate, db: Session = Depends(get_db)):
    if not db.get(Team, payload.team_id):
        raise HTTPException(404, "Team not found")
    if not db.get(Season, payload.season_id):
        raise HTTPException(404, "Season not found")
    obj = Player(
        **_normalize_contract_duration(
            normalize_player_financials(payload.model_dump())
        )
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@players_router.put(
    "/{player_id}", response_model=PlayerResponse, dependencies=[AdminDep]
)
def update_player(
    player_id: UUID, payload: PlayerUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Player, player_id)
    if not obj:
        raise HTTPException(404)
    data = normalize_player_financials(
        payload.model_dump(exclude_unset=True),
        fallback_market_value=float(obj.market_value or 0.0),
    )
    data = _normalize_contract_duration(
        data,
        fallback_total=int(obj.contract_years_total or 1),
        fallback_remaining=int(obj.contract_years_remaining or 1),
    )
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@players_router.delete("/{player_id}", status_code=204, dependencies=[AdminDep])
def delete_player(player_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Player, player_id)
    if not obj:
        raise HTTPException(404)
    db.delete(obj)
    db.commit()


@players_router.post(
    "/bulk", response_model=list[PlayerResponse], dependencies=[AdminDep]
)
def bulk_create_players(payload: PlayerBulkCreate, db: Session = Depends(get_db)):
    created: list[Player] = []
    for item in payload.players:
        if not db.get(Team, item.team_id):
            raise HTTPException(404, f"Team {item.team_id} not found")
        if not db.get(Season, item.season_id):
            raise HTTPException(404, f"Season {item.season_id} not found")
        obj = Player(
            **_normalize_contract_duration(
                normalize_player_financials(item.model_dump())
            )
        )
        db.add(obj)
        created.append(obj)
    db.commit()
    for obj in created:
        db.refresh(obj)
    return created
