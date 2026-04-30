from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from openpyxl import load_workbook


@dataclass(frozen=True)
class ScheduleMatch:
    home_team: str
    home_score: float | None
    away_score: float | None
    away_team: str
    result: str | None


@dataclass(frozen=True)
class ScheduleRound:
    league_round: int
    serie_a_round: int | None
    matches: list[ScheduleMatch]


@dataclass(frozen=True)
class StandingRow:
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


@dataclass(frozen=True)
class LeagueCalendarData:
    title: str
    source_url: str | None
    standings: list[StandingRow]
    rounds: list[ScheduleRound]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _rose_dir() -> Path:
    return _project_root() / "rose"


def _calendar_file() -> Path:
    return _rose_dir() / "Calendario_BUTTERATA-4SEASON-LEAGUE.xlsx"


def _standings_file() -> Path:
    return _rose_dir() / "Classifica_BUTTERATA-4SEASON-LEAGUE.xlsx"


def _parse_round_number(label: str) -> int:
    digits = "".join(char for char in label if char.isdigit())
    if not digits:
        raise ValueError(f"Unable to parse round number from {label!r}")
    return int(digits)


def _clean_text(value: object) -> str:
    return str(value).replace("�", "°").strip()


def _load_sheet(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing source file: {path}")
    return load_workbook(path, data_only=True).active


def _parse_calendar() -> tuple[str, str | None, list[ScheduleRound]]:
    sheet = _load_sheet(_calendar_file())
    title = _clean_text(sheet.cell(row=1, column=1).value or "Calendario")
    source_url = sheet.cell(row=2, column=1).value
    rounds: list[ScheduleRound] = []

    row = 4
    while row <= sheet.max_row:
        left_header = sheet.cell(row=row, column=1).value
        right_header = sheet.cell(row=row, column=7).value
        if left_header is None and right_header is None:
            row += 1
            continue

        for start_col, header_value, serie_a_col in (
            (1, left_header, 3),
            (7, right_header, 9),
        ):
            if not header_value:
                continue
            league_round = _parse_round_number(_clean_text(header_value))
            serie_a_value = sheet.cell(row=row, column=serie_a_col).value
            serie_a_round = (
                _parse_round_number(_clean_text(serie_a_value))
                if serie_a_value
                else None
            )
            matches: list[ScheduleMatch] = []

            for match_row in range(row + 1, min(row + 6, sheet.max_row + 1)):
                home_team = sheet.cell(row=match_row, column=start_col).value
                away_team = sheet.cell(row=match_row, column=start_col + 3).value
                result = sheet.cell(row=match_row, column=start_col + 4).value
                if not home_team and not away_team:
                    continue
                matches.append(
                    ScheduleMatch(
                        home_team=_clean_text(home_team or "-"),
                        home_score=(
                            float(sheet.cell(row=match_row, column=start_col + 1).value)
                            if sheet.cell(row=match_row, column=start_col + 1).value
                            is not None
                            else None
                        ),
                        away_score=(
                            float(sheet.cell(row=match_row, column=start_col + 2).value)
                            if sheet.cell(row=match_row, column=start_col + 2).value
                            is not None
                            else None
                        ),
                        away_team=_clean_text(away_team or "-"),
                        result=_clean_text(result) if result else None,
                    )
                )

            rounds.append(
                ScheduleRound(
                    league_round=league_round,
                    serie_a_round=serie_a_round,
                    matches=matches,
                )
            )

        row += 6

    return title, source_url, rounds


def _parse_standings() -> tuple[str, str | None, list[StandingRow]]:
    sheet = _load_sheet(_standings_file())
    title = _clean_text(sheet.cell(row=1, column=1).value or "Classifica")
    source_url = sheet.cell(row=2, column=1).value
    rows: list[StandingRow] = []

    for row in range(5, sheet.max_row + 1):
        position = sheet.cell(row=row, column=1).value
        team = sheet.cell(row=row, column=2).value
        if position is None or not team:
            continue
        rows.append(
            StandingRow(
                position=int(position),
                team=_clean_text(team),
                played=int(sheet.cell(row=row, column=4).value or 0),
                wins=int(sheet.cell(row=row, column=5).value or 0),
                draws=int(sheet.cell(row=row, column=6).value or 0),
                losses=int(sheet.cell(row=row, column=7).value or 0),
                goals_for=int(sheet.cell(row=row, column=8).value or 0),
                goals_against=int(sheet.cell(row=row, column=9).value or 0),
                goal_diff=int(sheet.cell(row=row, column=10).value or 0),
                points=int(sheet.cell(row=row, column=11).value or 0),
                total_points=float(sheet.cell(row=row, column=12).value or 0),
            )
        )

    return title, source_url, rows


@lru_cache(maxsize=1)
def get_league_calendar_data() -> LeagueCalendarData:
    standings_title, source_url, standings = _parse_standings()
    calendar_title, calendar_source_url, rounds = _parse_calendar()
    return LeagueCalendarData(
        title=standings_title or calendar_title,
        source_url=source_url or calendar_source_url,
        standings=standings,
        rounds=rounds,
    )
