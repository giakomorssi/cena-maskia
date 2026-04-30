from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.league import BalanceEntry, BalanceSheet, Fine, Player, Transfer
from app.services.balance_calc_service import (
    recompute_totals,
    replace_entries,
    roster_prepopulated_entries,
)
from app.services.trade_service import (
    AUTO_MARKET_CASH_TRANSFER,
    AUTO_MARKET_MINUS_TRANSFER,
    AUTO_MARKET_PLUS_TRANSFER,
)


@dataclass(frozen=True)
class StadiumOption:
    id: str
    name: str
    city: str
    revenue: float
    cost: float
    description: str


@dataclass(frozen=True)
class GuidedFieldDefinition:
    key: str
    label: str
    section: str
    description: str
    default_amount: float = 0.0


STADIUM_OPTIONS: tuple[StadiumOption, ...] = (
    StadiumOption(
        id="municipale",
        name="Stadio Comunale",
        city="Capoluogo",
        revenue=18.0,
        cost=6.0,
        description="Impianto base della lega, bilancio prudente ma stabile.",
    ),
    StadiumOption(
        id="arena",
        name="Arena Metropolitana",
        city="Metropoli",
        revenue=28.0,
        cost=11.0,
        description="Stadio premium con ricavi più alti e costi di gestione superiori.",
    ),
    StadiumOption(
        id="fortino",
        name="Fortino di Quartiere",
        city="Provincia",
        revenue=14.0,
        cost=4.0,
        description="Scelta compatta e sostenibile, meno ricavi ma struttura economica leggera.",
    ),
    StadiumOption(
        id="olimpico",
        name="Olimpico della Lega",
        city="Capitale",
        revenue=35.0,
        cost=15.0,
        description="Impianto di prestigio con ricavi massimi e costi elevati.",
    ),
)

GUIDED_FIELD_DEFINITIONS: tuple[GuidedFieldDefinition, ...] = (
    GuidedFieldDefinition(
        key="capitale_sociale",
        label="Capitale sociale",
        section="ricavi",
        description="Apporto iniziale della proprieta' previsto dal regolamento.",
        default_amount=500.0,
    ),
    GuidedFieldDefinition(
        key="sponsor",
        label="Sponsor",
        section="ricavi",
        description="Sponsorizzazioni, accordi commerciali o bonus di lega.",
    ),
    GuidedFieldDefinition(
        key="premi",
        label="Premi",
        section="ricavi",
        description="Premi piazzamento, coppa o bonus risultato della stagione.",
    ),
    GuidedFieldDefinition(
        key="plus_minus_manuale",
        label="Plus / Minus cessioni",
        section="plus_minus",
        description="Rettifiche manuali su plusvalenze e minusvalenze non coperte dagli automatismi.",
    ),
    GuidedFieldDefinition(
        key="costi_vari",
        label="Costi vari",
        section="costi",
        description="Iscrizione, consulenze, tasse e costi accessori non automatici.",
    ),
)


def stadium_options() -> list[StadiumOption]:
    return list(STADIUM_OPTIONS)


def stadium_option_map() -> dict[str, StadiumOption]:
    return {option.id: option for option in STADIUM_OPTIONS}


def guided_field_definitions() -> list[GuidedFieldDefinition]:
    return list(GUIDED_FIELD_DEFINITIONS)


def _entry_kind(entry: BalanceEntry | dict) -> str | None:
    meta = entry.meta if isinstance(entry, BalanceEntry) else entry.get("meta")
    if not isinstance(meta, dict):
        return None
    kind = meta.get("kind")
    return str(kind) if kind else None


def _entry_meta(entry: BalanceEntry | dict) -> dict:
    meta = entry.meta if isinstance(entry, BalanceEntry) else entry.get("meta")
    return meta if isinstance(meta, dict) else {}


def _entry_identity(entry: BalanceEntry | dict) -> str:
    serialized = _serialize_entry(entry)
    meta = _entry_meta(entry)
    kind = str(meta.get("kind") or serialized["label"])
    player_id = meta.get("player_id")
    stadium_id = meta.get("stadium_id")
    if player_id:
        return f"{kind}:{player_id}"
    if stadium_id:
        return f"{kind}:{stadium_id}"
    return kind


def _serialize_entry(entry: BalanceEntry | dict) -> dict:
    if isinstance(entry, BalanceEntry):
        return {
            "section": entry.section,
            "label": entry.label,
            "amount": float(entry.amount or 0.0),
            "meta": entry.meta or None,
        }
    return {
        "section": entry["section"],
        "label": entry["label"],
        "amount": float(entry.get("amount") or 0.0),
        "meta": entry.get("meta"),
    }


def _selected_stadium_id(entries: Iterable[BalanceEntry | dict]) -> str | None:
    for entry in entries:
        meta = _entry_meta(entry)
        if meta.get("kind") in {"stadium_revenue", "stadium_cost"} and meta.get(
            "stadium_id"
        ):
            return str(meta["stadium_id"])
    return None


def _guided_field_entry(field: GuidedFieldDefinition, amount: float) -> dict:
    return {
        "section": field.section,
        "label": field.label,
        "amount": float(amount),
        "meta": {"kind": field.key, "guided": True, "auto": False},
    }


def _build_transfer_entries(team_id: UUID, transfers: Iterable[Transfer]) -> list[dict]:
    sale_total = 0.0
    buy_total = 0.0
    cash_in_total = 0.0
    cash_out_total = 0.0
    plus_total = 0.0
    minus_total = 0.0
    for transfer in transfers:
        fee = float(transfer.fee or 0.0)
        if fee <= 0:
            continue
        if transfer.type == AUTO_MARKET_CASH_TRANSFER:
            if transfer.from_team_id == team_id:
                cash_out_total += fee
            if transfer.to_team_id == team_id:
                cash_in_total += fee
            continue
        if transfer.type == AUTO_MARKET_PLUS_TRANSFER:
            if transfer.from_team_id == team_id:
                plus_total += fee
            continue
        if transfer.type == AUTO_MARKET_MINUS_TRANSFER:
            if transfer.from_team_id == team_id:
                minus_total += fee
            continue
        if transfer.from_team_id == team_id:
            sale_total += fee
        if transfer.to_team_id == team_id:
            buy_total += fee

    entries: list[dict] = []
    if sale_total > 0:
        entries.append(
            {
                "section": "ricavi",
                "label": "Cessioni calciatori",
                "amount": sale_total,
                "meta": {"kind": "transfer_sales", "auto": True},
            }
        )
    if buy_total > 0:
        entries.append(
            {
                "section": "costi",
                "label": "Acquisto giocatori",
                "amount": buy_total,
                "meta": {"kind": "transfer_buys", "auto": True},
            }
        )
    if cash_in_total > 0:
        entries.append(
            {
                "section": "ricavi",
                "label": "Conguagli mercato in entrata",
                "amount": cash_in_total,
                "meta": {"kind": "trade_cash_in", "auto": True},
            }
        )
    if cash_out_total > 0:
        entries.append(
            {
                "section": "costi",
                "label": "Conguagli mercato in uscita",
                "amount": cash_out_total,
                "meta": {"kind": "trade_cash_out", "auto": True},
            }
        )
    if plus_total > 0:
        entries.append(
            {
                "section": "plus_minus",
                "label": "Plusvalenze mercato",
                "amount": plus_total,
                "meta": {"kind": "trade_plusvalenze", "auto": True},
            }
        )
    if minus_total > 0:
        entries.append(
            {
                "section": "plus_minus",
                "label": "Minusvalenze mercato",
                "amount": -minus_total,
                "meta": {"kind": "trade_minusvalenze", "auto": True},
            }
        )
    return entries


def _build_fine_entries(fines: Iterable[Fine]) -> list[dict]:
    total = sum(float(fine.amount or 0.0) for fine in fines)
    if total <= 0:
        return []
    return [
        {
            "section": "costi",
            "label": "Multe di lega",
            "amount": total,
            "meta": {"kind": "fines", "auto": True},
        }
    ]


def _build_stadium_entries(stadium_id: str | None) -> list[dict]:
    if not stadium_id:
        return []
    option = stadium_option_map().get(stadium_id)
    if not option:
        return []
    return [
        {
            "section": "ricavi",
            "label": f"Ricavi stadio · {option.name}",
            "amount": option.revenue,
            "meta": {
                "kind": "stadium_revenue",
                "stadium_id": option.id,
                "auto": True,
                "guided": True,
            },
        },
        {
            "section": "costi",
            "label": f"Costi stadio · {option.name}",
            "amount": option.cost,
            "meta": {
                "kind": "stadium_cost",
                "stadium_id": option.id,
                "auto": True,
                "guided": True,
            },
        },
    ]


def build_auto_entries(
    *,
    team_id: UUID,
    players: Iterable[Player],
    transfers: Iterable[Transfer],
    fines: Iterable[Fine],
    stadium_id: str | None,
) -> list[dict]:
    entries = roster_prepopulated_entries(players)
    entries.extend(_build_transfer_entries(team_id, transfers))
    entries.extend(_build_fine_entries(fines))
    entries.extend(_build_stadium_entries(stadium_id))
    return entries


def build_guided_manual_entries(
    entries: Iterable[BalanceEntry | dict],
) -> tuple[list[dict], list[dict]]:
    by_key: dict[str, dict] = {}
    extras: list[dict] = []
    definitions = {field.key: field for field in GUIDED_FIELD_DEFINITIONS}
    label_to_key = {field.label: field.key for field in GUIDED_FIELD_DEFINITIONS}

    for field in GUIDED_FIELD_DEFINITIONS:
        by_key[field.key] = _guided_field_entry(field, field.default_amount)

    for entry in entries:
        serialized = _serialize_entry(entry)
        meta = _entry_meta(entry)
        key = None
        if meta.get("guided") and meta.get("kind") in definitions:
            key = str(meta["kind"])
        elif serialized["label"] in label_to_key:
            key = label_to_key[serialized["label"]]

        if key and key in by_key:
            by_key[key] = _guided_field_entry(definitions[key], serialized["amount"])
        else:
            extras.append(serialized)

    return list(by_key.values()), extras


def split_entries(
    entries: Iterable[BalanceEntry | dict],
) -> tuple[list[dict], list[dict]]:
    auto_entries: list[dict] = []
    manual_entries: list[dict] = []
    for entry in entries:
        serialized = _serialize_entry(entry)
        meta = _entry_meta(entry)
        if meta.get("auto"):
            auto_entries.append(serialized)
        else:
            manual_entries.append(serialized)
    return auto_entries, manual_entries


def _issues_from_balance(
    *,
    balance: BalanceSheet | None,
    selected_stadium_id: str | None,
    manual_entries: list[dict],
    expected_auto_entries: list[dict],
    actual_entries: Iterable[BalanceEntry | dict],
    roster_count: int,
) -> list[dict]:
    issues: list[dict] = []
    manual_by_kind = {
        (_entry_meta(entry).get("kind") or entry["label"]): entry
        for entry in manual_entries
    }
    actual_auto_by_kind = {
        _entry_identity(entry): _serialize_entry(entry)
        for entry in actual_entries
        if _entry_meta(entry).get("auto")
    }

    if not selected_stadium_id:
        issues.append(
            {
                "code": "stadium_missing",
                "label": "Stadio non selezionato",
                "detail": "Seleziona uno stadio per calcolare automaticamente ricavi e costi stadio.",
                "severity": "warning",
            }
        )

    for required in ("capitale_sociale", "sponsor", "premi"):
        entry = manual_by_kind.get(required)
        if not entry or float(entry.get("amount") or 0.0) <= 0:
            label = next(
                field.label
                for field in GUIDED_FIELD_DEFINITIONS
                if field.key == required
            )
            issues.append(
                {
                    "code": f"missing_{required}",
                    "label": f"{label} da verificare",
                    "detail": f"La voce '{label}' è a zero o non compilata.",
                    "severity": "warning",
                }
            )

    for expected in expected_auto_entries:
        identity = _entry_identity(expected)
        kind = _entry_meta(expected).get("kind") or expected["label"]
        actual = actual_auto_by_kind.get(identity)
        if not actual:
            issues.append(
                {
                    "code": f"missing_auto_{identity}",
                    "label": f"Voce auto mancante: {expected['label']}",
                    "detail": "Una voce automatica attesa non è presente nel bilancio corrente.",
                    "severity": "warning",
                }
            )
            continue
        if (
            abs(
                float(actual.get("amount") or 0.0)
                - float(expected.get("amount") or 0.0)
            )
            > 0.01
        ):
            issues.append(
                {
                    "code": f"mismatch_auto_{identity}",
                    "label": f"Voce auto incoerente: {expected['label']}",
                    "detail": "Il valore presente non coincide con il calcolo automatico atteso.",
                    "severity": "warning",
                }
            )

    if balance and balance.utile < 0:
        issues.append(
            {
                "code": "negative_result",
                "label": "Bilancio in perdita",
                "detail": balance.sanction_notes
                or "Il risultato netto è negativo e genera una sanzione.",
                "severity": (
                    "critical"
                    if balance.sanction_level in {"medium", "heavy"}
                    else "warning"
                ),
            }
        )

    if roster_count == 0:
        issues.append(
            {
                "code": "empty_roster",
                "label": "Rosa vuota",
                "detail": "La squadra non ha giocatori attivi nella stagione corrente.",
                "severity": "critical",
            }
        )

    return issues


def _load_supporting_data(
    db: Session, team_id: UUID, season_id: UUID
) -> tuple[list[Player], list[Transfer], list[Fine]]:
    players = (
        db.execute(
            select(Player).where(
                Player.team_id == team_id, Player.season_id == season_id
            )
        )
        .scalars()
        .all()
    )
    transfers = (
        db.execute(select(Transfer).where(Transfer.season_id == season_id))
        .scalars()
        .all()
    )
    fines = (
        db.execute(
            select(Fine).where(Fine.team_id == team_id, Fine.season_id == season_id)
        )
        .scalars()
        .all()
    )
    return players, transfers, fines


def sync_balance_draft(db: Session, balance: BalanceSheet) -> BalanceSheet:
    players, transfers, fines = _load_supporting_data(
        db, balance.team_id, balance.season_id
    )
    _, manual_entries = split_entries(balance.entries)
    selected_stadium_id = _selected_stadium_id(balance.entries)
    auto_entries = build_auto_entries(
        team_id=balance.team_id,
        players=players,
        transfers=transfers,
        fines=fines,
        stadium_id=selected_stadium_id,
    )
    replace_entries(db, balance, [*manual_entries, *auto_entries])
    recompute_totals(balance)
    db.flush()
    db.refresh(balance)
    return balance


def normalize_guided_entries(
    db: Session, balance: BalanceSheet, payload_entries: list[dict]
) -> list[dict]:
    players, transfers, fines = _load_supporting_data(
        db, balance.team_id, balance.season_id
    )
    _, manual_entries = split_entries(payload_entries)
    selected_stadium_id = _selected_stadium_id(payload_entries)
    auto_entries = build_auto_entries(
        team_id=balance.team_id,
        players=players,
        transfers=transfers,
        fines=fines,
        stadium_id=selected_stadium_id,
    )
    return [*manual_entries, *auto_entries]


def build_guided_payload(db: Session, balance: BalanceSheet) -> dict:
    if balance.status == "draft":
        sync_balance_draft(db, balance)
    players, transfers, fines = _load_supporting_data(
        db, balance.team_id, balance.season_id
    )
    auto_entries, manual_entries = split_entries(balance.entries)
    guided_fields, extra_manual_entries = build_guided_manual_entries(manual_entries)
    selected_stadium_id = _selected_stadium_id(balance.entries)
    expected_auto_entries = build_auto_entries(
        team_id=balance.team_id,
        players=players,
        transfers=transfers,
        fines=fines,
        stadium_id=selected_stadium_id,
    )
    issues = _issues_from_balance(
        balance=balance,
        selected_stadium_id=selected_stadium_id,
        manual_entries=guided_fields,
        expected_auto_entries=expected_auto_entries,
        actual_entries=balance.entries,
        roster_count=len([player for player in players if player.is_active]),
    )
    return {
        "selected_stadium_id": selected_stadium_id,
        "stadiums": [option.__dict__ for option in STADIUM_OPTIONS],
        "guided_fields": [
            {
                **field,
                "description": next(
                    definition.description
                    for definition in GUIDED_FIELD_DEFINITIONS
                    if definition.key == _entry_meta(field).get("kind")
                ),
            }
            for field in guided_fields
        ],
        "auto_entries": auto_entries,
        "extra_manual_entries": extra_manual_entries,
        "issues": issues,
    }


def build_admin_balance_issues(
    *, db: Session, team_id: UUID, season_id: UUID, balance: BalanceSheet | None
) -> list[dict]:
    if balance is None:
        return [
            {
                "code": "balance_missing",
                "label": "Bilancio mancante",
                "detail": "La squadra non ha ancora inviato il bilancio della stagione corrente.",
                "severity": "critical",
            }
        ]
    players, transfers, fines = _load_supporting_data(db, team_id, season_id)
    auto_entries, manual_entries = split_entries(balance.entries)
    guided_fields, _ = build_guided_manual_entries(manual_entries)
    selected_stadium_id = _selected_stadium_id(balance.entries)
    expected_auto_entries = build_auto_entries(
        team_id=team_id,
        players=players,
        transfers=transfers,
        fines=fines,
        stadium_id=selected_stadium_id,
    )
    return _issues_from_balance(
        balance=balance,
        selected_stadium_id=selected_stadium_id,
        manual_entries=guided_fields,
        expected_auto_entries=expected_auto_entries,
        actual_entries=balance.entries,
        roster_count=len([player for player in players if player.is_active]),
    )
