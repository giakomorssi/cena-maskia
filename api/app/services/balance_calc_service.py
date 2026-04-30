"""On-site balance computation: roster prepopulation, totals, sanctions."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.league import BalanceEntry, BalanceSheet, Player
from app.services.balance_service import SanctionService
from app.services.player_finance_rules import (
    LEGACY_FASCIA_AMMORTIZATION,
    FASCIA_RULES,
    fascia_from_cost,
    salary_from_cost,
)

# fascia → base ammortamento percentuale
_FASCIA_PCT = {
    **{str(rule["key"]): float(rule["amm_pct"]) for rule in FASCIA_RULES},
    **LEGACY_FASCIA_AMMORTIZATION,
}

# acquisition_type → fattore moltiplicativo sull'ammortamento base
_ACQUISITION_FACTOR = {
    "owned": 1.0,
    "loan_with_obligation": 1.0,
    "loan_with_right": 0.5,
    "loan_dry": 0.0,
    "sold_definitively": 0.0,
}


def amortization_for_player(player: Player) -> float:
    market_value = float(player.market_value or 0.0)
    normalized_fascia = (
        fascia_from_cost(market_value) if market_value > 0 else player.fascia
    )
    base = _FASCIA_PCT.get(normalized_fascia, 1.0)
    factor = _ACQUISITION_FACTOR.get(player.acquisition_type, 1.0)
    contract_years = max(1, min(int(player.contract_years_total or 1), 5))
    return (market_value * base * factor) / contract_years


def _normalized_player_financials(player: Player) -> dict:
    market_value = float(player.market_value or 0.0)
    contract_years_total = max(1, min(int(player.contract_years_total or 1), 5))
    contract_years_remaining = max(
        1,
        min(
            int(player.contract_years_remaining or contract_years_total),
            contract_years_total,
        ),
    )
    if market_value > 0:
        normalized_fascia = fascia_from_cost(market_value)
        normalized_salary = salary_from_cost(market_value)
    else:
        normalized_fascia = player.fascia
        normalized_salary = float(player.salary or 0.0)
    return {
        "market_value": market_value,
        "fascia": normalized_fascia,
        "salary": normalized_salary,
        "contract_years_total": contract_years_total,
        "contract_years_remaining": contract_years_remaining,
    }


def roster_prepopulated_entries(players: Iterable[Player]) -> list[dict]:
    """Build a list of seed entries for a balance derived from the roster."""
    entries: list[dict] = []
    for p in players:
        if not p.is_active:
            continue
        if p.acquisition_type == "sold_definitively":
            continue
        financials = _normalized_player_financials(p)
        if financials["salary"] > 0:
            entries.append(
                {
                    "section": "costi",
                    "label": f"Stipendio · {p.name}",
                    "amount": float(financials["salary"]),
                    "meta": {
                        "player_id": str(p.id),
                        "kind": "salary",
                        "auto": True,
                        "role": p.role,
                        "fascia": financials["fascia"],
                        "market_value": financials["market_value"],
                        "contract_years_total": financials["contract_years_total"],
                        "contract_years_remaining": financials[
                            "contract_years_remaining"
                        ],
                        "acquisition_type": p.acquisition_type,
                    },
                }
            )
        amm = amortization_for_player(p)
        if amm > 0:
            entries.append(
                {
                    "section": "ammortamenti",
                    "label": f"Ammortamento · {p.name}",
                    "amount": amm,
                    "meta": {
                        "player_id": str(p.id),
                        "kind": "amm",
                        "auto": True,
                        "role": p.role,
                        "fascia": financials["fascia"],
                        "market_value": financials["market_value"],
                        "salary": financials["salary"],
                        "contract_years_total": financials["contract_years_total"],
                        "contract_years_remaining": financials[
                            "contract_years_remaining"
                        ],
                        "acquisition_type": p.acquisition_type,
                        "base_pct": _FASCIA_PCT.get(financials["fascia"], 1.0),
                        "acq_factor": _ACQUISITION_FACTOR.get(p.acquisition_type, 1.0),
                    },
                }
            )
    return entries


def recompute_totals(balance: BalanceSheet) -> None:
    """Recompute total_* and utile from current entries; write sanction fields."""
    totals = {"ricavi": 0.0, "costi": 0.0, "ammortamenti": 0.0, "plus_minus": 0.0}
    for e in balance.entries:
        if e.section in totals:
            totals[e.section] += float(e.amount or 0.0)
    balance.total_ricavi = totals["ricavi"]
    balance.total_costi = totals["costi"]
    balance.total_ammortamenti = totals["ammortamenti"]
    balance.total_plus_minus = totals["plus_minus"]
    balance.utile = (
        totals["ricavi"]
        + totals["plus_minus"]
        - totals["costi"]
        - totals["ammortamenti"]
    )
    sanction = SanctionService.evaluate(balance.utile)
    balance.sanction_level = sanction.level
    balance.sanction_points = sanction.points
    balance.sanction_notes = sanction.notes


def replace_entries(
    db: Session, balance: BalanceSheet, payload_entries: list[dict]
) -> None:
    """Delete current entries and replace with the provided list."""
    for entry in list(balance.entries):
        db.delete(entry)
    db.flush()
    balance.entries = []
    for item in payload_entries:
        db.add(
            BalanceEntry(
                balance_sheet_id=balance.id,
                section=item["section"],
                label=item["label"],
                amount=float(item.get("amount") or 0.0),
                meta=item.get("meta"),
            )
        )
    db.flush()
    db.refresh(balance)


def get_or_create_draft(db: Session, *, team_id: UUID, season_id: UUID) -> BalanceSheet:
    """Return existing balance for (team, season) or create a draft from roster."""
    existing = db.execute(
        select(BalanceSheet).where(
            BalanceSheet.team_id == team_id,
            BalanceSheet.season_id == season_id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    sheet = BalanceSheet(
        team_id=team_id,
        season_id=season_id,
        status="draft",
    )
    db.add(sheet)
    db.flush()

    players = (
        db.execute(
            select(Player).where(
                Player.team_id == team_id, Player.season_id == season_id
            )
        )
        .scalars()
        .all()
    )
    seed = roster_prepopulated_entries(players)
    for item in seed:
        db.add(
            BalanceEntry(
                balance_sheet_id=sheet.id,
                section=item["section"],
                label=item["label"],
                amount=item["amount"],
                meta=item["meta"],
            )
        )
    db.flush()
    db.refresh(sheet)
    recompute_totals(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet
