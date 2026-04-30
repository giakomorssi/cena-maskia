"""Mercato workflow: validate proposals, ratify (apply diff to roster + Transfer)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from math import isclose
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.league import (
    Player,
    TradeProposal,
    TradeProposalItem,
    Transfer,
)
from app.services.player_finance_rules import normalize_player_financials

_TRANSFER_TYPE_MAP = {
    "owned": "cessione",
    "loan_dry": "prestito_secco",
    "loan_with_right": "prestito_diritto",
    "loan_with_obligation": "prestito_obbligo",
}

AUTO_MARKET_CASH_TRANSFER = "auto_market_cash"
AUTO_MARKET_PLUS_TRANSFER = "auto_market_plusvalenza"
AUTO_MARKET_MINUS_TRANSFER = "auto_market_minusvalenza"


def is_auto_market_transfer(transfer_type: str | None) -> bool:
    return transfer_type in {
        AUTO_MARKET_CASH_TRANSFER,
        AUTO_MARKET_PLUS_TRANSFER,
        AUTO_MARKET_MINUS_TRANSFER,
    }


def _player_economic_value(
    item: TradeProposalItem, current_market_value: float
) -> float:
    acquisition_type = item.acquisition_type_after or "owned"
    if acquisition_type in {"loan_dry", "loan_with_right"}:
        return 0.0
    if item.market_value_after is not None:
        return max(0.0, float(item.market_value_after))
    return max(0.0, current_market_value)


def validate_ownership(db: Session, proposal: TradeProposal) -> None:
    """Ensure each item's player currently belongs to the correct side."""
    for item in proposal.items:
        player = db.get(Player, item.player_id)
        if not player:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Player {item.player_id} not found",
            )
        if (
            item.direction == "from_proposer"
            and player.team_id != proposal.from_team_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Player '{player.name}' is no longer in proposer's roster",
            )
        if (
            item.direction == "from_counterparty"
            and player.team_id != proposal.to_team_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Player '{player.name}' is no longer in counterparty's roster",
            )


def apply_proposal(db: Session, proposal: TradeProposal) -> list[Transfer]:
    """Apply a ratified proposal: move players, update fields, create Transfers.

    Caller must commit the session.
    """
    validate_ownership(db, proposal)

    transfers: list[Transfer] = []
    for item in proposal.items:
        player = db.get(Player, item.player_id)
        if player is None:
            continue

        if item.direction == "from_proposer":
            new_team_id = proposal.to_team_id
            old_team_id = proposal.from_team_id
        else:
            new_team_id = proposal.from_team_id
            old_team_id = proposal.to_team_id

        previous_market_value = float(player.market_value or 0.0)
        player_value = _player_economic_value(item, previous_market_value)

        player.team_id = new_team_id
        player.acquisition_type = item.acquisition_type_after
        player.acquisition_season_id = proposal.season_id
        normalized_financials = normalize_player_financials(
            (
                {"market_value": item.market_value_after}
                if item.market_value_after is not None
                else (
                    {"salary": item.salary_after}
                    if item.salary_after is not None
                    else {}
                )
            ),
            fallback_market_value=float(player.market_value or 0.0),
        )
        for field in ("market_value", "salary", "fascia"):
            if field in normalized_financials:
                setattr(player, field, normalized_financials[field])
        if item.contract_years_after is not None:
            player.contract_years_total = int(item.contract_years_after)
            player.contract_years_remaining = int(item.contract_years_after)
        player.is_active = True

        transfer_type = _TRANSFER_TYPE_MAP.get(
            item.acquisition_type_after, item.acquisition_type_after
        )
        transfer = Transfer(
            season_id=proposal.season_id,
            from_team_id=old_team_id,
            to_team_id=new_team_id,
            player_name=player.name,
            fee=player_value,
            type=transfer_type,
            transfer_date=date.today(),
            notes=f"Proposta {proposal.id}",
        )
        db.add(transfer)
        transfers.append(transfer)

        delta = player_value - previous_market_value
        if player_value > 0 and not isclose(delta, 0.0, abs_tol=1e-9):
            plus_minus_transfer = Transfer(
                season_id=proposal.season_id,
                from_team_id=old_team_id,
                to_team_id=None,
                player_name=player.name,
                fee=abs(delta),
                type=(
                    AUTO_MARKET_PLUS_TRANSFER
                    if delta > 0
                    else AUTO_MARKET_MINUS_TRANSFER
                ),
                transfer_date=date.today(),
                notes=f"Automatismo bilancio proposta {proposal.id}",
            )
            db.add(plus_minus_transfer)
            transfers.append(plus_minus_transfer)

    cash_amount = max(0.0, float(proposal.cash_amount or 0.0))
    if cash_amount > 0:
        cash_transfer = Transfer(
            season_id=proposal.season_id,
            from_team_id=proposal.from_team_id,
            to_team_id=proposal.to_team_id,
            player_name="Conguaglio mercato",
            fee=cash_amount,
            type=AUTO_MARKET_CASH_TRANSFER,
            transfer_date=date.today(),
            notes=f"Automatismo bilancio proposta {proposal.id}",
        )
        db.add(cash_transfer)
        transfers.append(cash_transfer)

    proposal.status = "ratified"
    proposal.ratified_at = datetime.now(timezone.utc)
    db.flush()
    return transfers
