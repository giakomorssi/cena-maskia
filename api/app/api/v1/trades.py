"""Trade proposals router. Three-state workflow: proposed → accepted → ratified."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import (
    get_current_team,
    optional_admin,
    optional_team,
    require_admin,
)
from app.database import get_db
from app.models.league import (
    BalanceSheet,
    Player,
    Season,
    Team,
    TradeProposal,
    TradeProposalItem,
)
from app.schemas.league import (
    TradeProposalActionPayload,
    TradeProposalCreate,
    TradeProposalItemResponse,
    TradeProposalResponse,
)
from app.services.balance_guided_service import sync_balance_draft
from app.services.trade_service import apply_proposal, validate_ownership

trades_router = APIRouter(prefix="/trades", tags=["Trades"])

AdminDep = Depends(require_admin)
TeamDep = Depends(get_current_team)


def _decorate(db: Session, proposal: TradeProposal) -> TradeProposalResponse:
    items: list[TradeProposalItemResponse] = []
    for item in proposal.items:
        player = db.get(Player, item.player_id)
        items.append(
            TradeProposalItemResponse(
                id=item.id,
                proposal_id=item.proposal_id,
                player_id=item.player_id,
                direction=item.direction,
                acquisition_type_after=item.acquisition_type_after,
                contract_years_after=item.contract_years_after,
                salary_after=item.salary_after,
                market_value_after=item.market_value_after,
                player_name=player.name if player else None,
                player_role=player.role if player else None,
            )
        )
    from_team = db.get(Team, proposal.from_team_id)
    to_team = db.get(Team, proposal.to_team_id)
    return TradeProposalResponse(
        id=proposal.id,
        season_id=proposal.season_id,
        from_team_id=proposal.from_team_id,
        to_team_id=proposal.to_team_id,
        kind=proposal.kind,
        status=proposal.status,
        cash_amount=proposal.cash_amount or 0.0,
        notes=proposal.notes,
        admin_notes=proposal.admin_notes,
        created_at=proposal.created_at,
        responded_at=proposal.responded_at,
        ratified_at=proposal.ratified_at,
        items=items,
        from_team_name=from_team.name if from_team else None,
        to_team_name=to_team.name if to_team else None,
    )


def _load_proposal(db: Session, proposal_id: UUID) -> TradeProposal:
    obj = db.execute(
        select(TradeProposal)
        .options(selectinload(TradeProposal.items))
        .where(TradeProposal.id == proposal_id)
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404)
    return obj


def _ensure_party(team: Team, proposal: TradeProposal) -> str:
    if team.id == proposal.from_team_id:
        return "proposer"
    if team.id == proposal.to_team_id:
        return "counterparty"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not part of this proposal",
    )


@trades_router.get("/", response_model=list[TradeProposalResponse])
def list_trades(
    season_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access trade proposals",
        )

    stmt = select(TradeProposal).options(selectinload(TradeProposal.items))
    if season_id:
        stmt = stmt.where(TradeProposal.season_id == season_id)
    if status_filter:
        stmt = stmt.where(TradeProposal.status == status_filter)
    if not is_admin and current_team:
        stmt = stmt.where(
            or_(
                TradeProposal.from_team_id == current_team.id,
                TradeProposal.to_team_id == current_team.id,
            )
        )
    rows = db.execute(stmt.order_by(TradeProposal.created_at.desc())).scalars().all()
    return [_decorate(db, r) for r in rows]


@trades_router.get("/{proposal_id}", response_model=TradeProposalResponse)
def get_trade(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    proposal = _load_proposal(db, proposal_id)
    if not is_admin:
        if not current_team:
            raise HTTPException(401, "Authentication required")
        if current_team.id not in (proposal.from_team_id, proposal.to_team_id):
            raise HTTPException(403, "Not part of this proposal")
    return _decorate(db, proposal)


@trades_router.post("/", response_model=TradeProposalResponse, status_code=201)
def create_trade(
    payload: TradeProposalCreate,
    db: Session = Depends(get_db),
    team: Team = TeamDep,
):
    if payload.to_team_id == team.id:
        raise HTTPException(400, "Cannot propose a trade to yourself")
    if not db.get(Team, payload.to_team_id):
        raise HTTPException(404, "Counterparty team not found")
    if not db.get(Season, payload.season_id):
        raise HTTPException(404, "Season not found")
    if not payload.items:
        raise HTTPException(400, "Trade must include at least one item")

    proposal = TradeProposal(
        season_id=payload.season_id,
        from_team_id=team.id,
        to_team_id=payload.to_team_id,
        kind=payload.kind,
        status="proposed",
        cash_amount=payload.cash_amount or 0.0,
        notes=payload.notes,
    )
    db.add(proposal)
    db.flush()

    for item in payload.items:
        player = db.get(Player, item.player_id)
        if not player:
            raise HTTPException(404, f"Player {item.player_id} not found")
        if item.direction == "from_proposer" and player.team_id != team.id:
            raise HTTPException(
                400, f"Player '{player.name}' does not belong to your roster"
            )
        if (
            item.direction == "from_counterparty"
            and player.team_id != payload.to_team_id
        ):
            raise HTTPException(
                400, f"Player '{player.name}' is not in counterparty's roster"
            )
        db.add(
            TradeProposalItem(
                proposal_id=proposal.id,
                player_id=item.player_id,
                direction=item.direction,
                acquisition_type_after=item.acquisition_type_after,
                contract_years_after=item.contract_years_after,
                salary_after=item.salary_after,
                market_value_after=item.market_value_after,
            )
        )
    db.commit()
    proposal = _load_proposal(db, proposal.id)
    return _decorate(db, proposal)


@trades_router.post("/{proposal_id}/accept", response_model=TradeProposalResponse)
def accept_trade(
    proposal_id: UUID,
    payload: TradeProposalActionPayload | None = None,
    db: Session = Depends(get_db),
    team: Team = TeamDep,
):
    proposal = _load_proposal(db, proposal_id)
    if team.id != proposal.to_team_id:
        raise HTTPException(403, "Only the counterparty can accept this proposal")
    if proposal.status != "proposed":
        raise HTTPException(
            409, f"Cannot accept a proposal in status '{proposal.status}'"
        )
    proposal.status = "accepted"
    proposal.responded_at = datetime.now(timezone.utc)
    if payload and payload.notes:
        proposal.notes = (proposal.notes or "") + f"\n[risposta] {payload.notes}"
    db.commit()
    db.refresh(proposal)
    return _decorate(db, proposal)


@trades_router.post("/{proposal_id}/reject", response_model=TradeProposalResponse)
def reject_trade(
    proposal_id: UUID,
    payload: TradeProposalActionPayload | None = None,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    proposal = _load_proposal(db, proposal_id)
    if not is_admin:
        role = _ensure_party(current_team, proposal)
        if proposal.status not in ("proposed", "accepted"):
            raise HTTPException(
                409, f"Cannot reject a proposal in status '{proposal.status}'"
            )
        if role == "proposer" and proposal.status != "proposed":
            raise HTTPException(
                409, "Proposer can only reject before counterparty has accepted"
            )
    else:
        if proposal.status not in ("proposed", "accepted"):
            raise HTTPException(
                409, f"Cannot reject a proposal in status '{proposal.status}'"
            )
    proposal.status = "rejected"
    proposal.responded_at = datetime.now(timezone.utc)
    if payload and payload.notes:
        proposal.notes = (proposal.notes or "") + f"\n[rifiuto] {payload.notes}"
    db.commit()
    db.refresh(proposal)
    return _decorate(db, proposal)


@trades_router.post("/{proposal_id}/cancel", response_model=TradeProposalResponse)
def cancel_trade(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    team: Team = TeamDep,
):
    proposal = _load_proposal(db, proposal_id)
    if team.id != proposal.from_team_id:
        raise HTTPException(403, "Only the proposer can cancel this proposal")
    if proposal.status != "proposed":
        raise HTTPException(
            409, f"Cannot cancel a proposal in status '{proposal.status}'"
        )
    proposal.status = "cancelled"
    proposal.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)
    return _decorate(db, proposal)


@trades_router.post(
    "/{proposal_id}/ratify",
    response_model=TradeProposalResponse,
    dependencies=[AdminDep],
)
def ratify_trade(
    proposal_id: UUID,
    payload: TradeProposalActionPayload | None = None,
    db: Session = Depends(get_db),
):
    proposal = _load_proposal(db, proposal_id)
    if proposal.status != "accepted":
        raise HTTPException(
            409,
            f"Only accepted proposals can be ratified (current: '{proposal.status}')",
        )
    apply_proposal(db, proposal)
    draft_sheets = (
        db.execute(
            select(BalanceSheet).where(
                BalanceSheet.season_id == proposal.season_id,
                BalanceSheet.team_id.in_([proposal.from_team_id, proposal.to_team_id]),
                BalanceSheet.status == "draft",
            )
        )
        .scalars()
        .all()
    )
    for sheet in draft_sheets:
        sync_balance_draft(db, sheet)
    if payload and payload.admin_notes:
        proposal.admin_notes = payload.admin_notes
    db.commit()
    db.refresh(proposal)
    return _decorate(db, proposal)


@trades_router.delete("/{proposal_id}", status_code=204)
def delete_trade(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    """Permanently delete a rejected or cancelled proposal."""
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    proposal = _load_proposal(db, proposal_id)
    if not is_admin:
        _ensure_party(current_team, proposal)
    if proposal.status not in ("rejected", "cancelled"):
        raise HTTPException(
            409, "Only rejected or cancelled proposals can be permanently deleted"
        )
    db.delete(proposal)
    db.commit()


@trades_router.post("/{proposal_id}/restore", response_model=TradeProposalResponse)
def restore_trade(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(optional_admin),
    current_team: Team | None = Depends(optional_team),
):
    """Restore a rejected or cancelled proposal back to 'proposed' status."""
    if not is_admin and not current_team:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    proposal = _load_proposal(db, proposal_id)
    if not is_admin:
        role = _ensure_party(current_team, proposal)
        if role != "proposer":
            raise HTTPException(403, "Only the proposer can restore a proposal")
    if proposal.status not in ("rejected", "cancelled"):
        raise HTTPException(409, "Only rejected or cancelled proposals can be restored")
    proposal.status = "proposed"
    proposal.responded_at = None
    db.commit()
    db.refresh(proposal)
    return _decorate(db, proposal)
