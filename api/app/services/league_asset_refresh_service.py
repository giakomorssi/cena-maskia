from __future__ import annotations

from dataclasses import dataclass
import re
import ssl
from typing import Literal
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.services.league_calendar_service import (
    parse_calendar_excel,
    parse_rose_excel,
    parse_standings_excel,
)

LeagueAssetKind = Literal["classifica", "calendar", "rose"]
SourceKind = Literal["excel", "html"]

_PAGE_SEGMENTS: dict[LeagueAssetKind, str] = {
    "classifica": "classifica",
    "calendar": "calendario",
    "rose": "rose",
}

_EXPLICIT_EXPORT_URLS: dict[LeagueAssetKind, str | None] = {
    "classifica": settings.fantacalcio_classifica_export_url,
    "calendar": settings.fantacalcio_calendar_export_url,
    "rose": settings.fantacalcio_rose_export_url,
}

_GENERIC_EXPORT_SUFFIXES = (
    "excel",
    "xlsx",
    "download",
    "export",
    "scarica",
)


class RemoteLeagueAssetError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemoteLeagueAssetFetchResult:
    kind: LeagueAssetKind
    source_kind: SourceKind
    source_url: str
    imported_rows: list[dict]


def refresh_remote_league_asset(kind: LeagueAssetKind) -> RemoteLeagueAssetFetchResult:
    if kind == "rose":
        raise RemoteLeagueAssetError(
            "Le rose possono essere aggiornate solo tramite upload Excel"
        )

    if kind == "calendar":
        source_url = _build_league_home_url()
        parsed_rows = parse_latest_calendar_round_html(_fetch_text(source_url))
        if parsed_rows:
            return RemoteLeagueAssetFetchResult(
                kind=kind,
                source_kind="html",
                source_url=source_url,
                imported_rows=parsed_rows,
            )
        raise RemoteLeagueAssetError(
            "Impossibile ricavare l'ultima giornata del calendario dalla pagina pubblica della lega"
        )

    page_url = _build_page_url(kind)
    page_html = _fetch_text(page_url)

    last_error: Exception | None = None
    for candidate_url in _iter_candidate_urls(kind, page_url, page_html):
        try:
            content = _fetch_binary(candidate_url)
            parsed_rows = _parse_excel_asset(kind, content)
            if parsed_rows:
                return RemoteLeagueAssetFetchResult(
                    kind=kind,
                    source_kind="excel",
                    source_url=candidate_url,
                    imported_rows=parsed_rows,
                )
        except Exception as exc:  # pragma: no cover - exercised through callers
            last_error = exc

    if kind == "classifica":
        parsed_rows = parse_standings_html(page_html)
        if parsed_rows:
            return RemoteLeagueAssetFetchResult(
                kind=kind,
                source_kind="html",
                source_url=page_url,
                imported_rows=parsed_rows,
            )

    details = f": {last_error}" if last_error else ""
    raise RemoteLeagueAssetError(
        f"Impossibile recuperare l'asset remoto '{kind}' da Fantacalcio{details}"
    )


def parse_standings_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [
                _clean_cell(td.get_text(" ", strip=True))
                for td in tr.find_all(["td", "th"])
            ]
            cells = [cell for cell in cells if cell]
            parsed = _parse_standings_row(cells)
            if parsed is not None:
                rows.append(parsed)

    seen_positions = set()
    unique_rows = []
    for row in rows:
        if row["position"] in seen_positions:
            continue
        seen_positions.add(row["position"])
        unique_rows.append(row)

    return unique_rows


def parse_latest_calendar_round_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    widget = _find_latest_calendar_widget(soup)
    if widget is None:
        return []

    title = _clean_cell(widget.select_one(".widget-title").get_text(" ", strip=True))
    round_numbers = [int(value) for value in re.findall(r"(\d+)", title)]
    if not round_numbers:
        return []

    league_round = round_numbers[0]
    serie_a_round = round_numbers[1] if len(round_numbers) > 1 else None
    matches = []
    for index, match in enumerate(widget.select("li.match")):
        home_team = match.select_one(".team-home .team-name")
        away_team = match.select_one(".team-away .team-name")
        if home_team is None or away_team is None:
            continue

        home_score = _parse_optional_score(match.select_one(".team-home .team-score"))
        away_score = _parse_optional_score(match.select_one(".team-away .team-score"))
        result = (
            f"{int(home_score)}-{int(away_score)}"
            if home_score is not None and away_score is not None
            else None
        )
        matches.append(
            {
                "match_order": index,
                "home_team": _clean_cell(home_team.get_text(" ", strip=True)),
                "away_team": _clean_cell(away_team.get_text(" ", strip=True)),
                "home_score": home_score,
                "away_score": away_score,
                "result": result,
            }
        )

    if not matches:
        return []

    return [
        {
            "league_round": league_round,
            "serie_a_round": serie_a_round,
            "matches": matches,
        }
    ]


def _parse_standings_row(cells: list[str]) -> dict | None:
    if len(cells) < 11:
        return None

    position_index = next(
        (index for index, value in enumerate(cells) if _looks_like_int(value)),
        None,
    )
    if position_index is None:
        return None

    team_index = next(
        (
            index
            for index in range(position_index + 1, len(cells))
            if re.search(r"[A-Za-zÀ-ÿ]", cells[index])
        ),
        None,
    )
    if team_index is None:
        return None

    numeric_values = [
        _parse_number(value)
        for value in cells[team_index + 1 :]
        if _looks_like_number(value)
    ]
    if len(numeric_values) < 9:
        return None

    return {
        "position": int(_parse_number(cells[position_index])),
        "team_name": _normalize_team_name(cells[team_index]),
        "played": int(numeric_values[0]),
        "wins": int(numeric_values[1]),
        "draws": int(numeric_values[2]),
        "losses": int(numeric_values[3]),
        "goals_for": int(numeric_values[4]),
        "goals_against": int(numeric_values[5]),
        "goal_diff": int(numeric_values[6]),
        "points": int(numeric_values[7]),
        "total_points": float(numeric_values[8]),
    }


def _find_latest_calendar_widget(soup: BeautifulSoup):
    for widget in soup.select(".widget"):
        title = widget.select_one(".widget-title")
        if title is None:
            continue
        title_text = _clean_cell(title.get_text(" ", strip=True)).lower()
        if "ultima giornata" in title_text and widget.select("li.match"):
            return widget

    for widget in soup.select(".widget"):
        title = widget.select_one(".widget-title")
        if title is None:
            continue
        title_text = _clean_cell(title.get_text(" ", strip=True)).lower()
        if title_text.startswith("ultima giornata"):
            return widget
    return None


def _parse_excel_asset(kind: LeagueAssetKind, content: bytes) -> list[dict]:
    if kind == "classifica":
        return parse_standings_excel(content)
    if kind == "calendar":
        return parse_calendar_excel(content)
    return parse_rose_excel(content)


def _iter_candidate_urls(kind: LeagueAssetKind, page_url: str, html: str) -> list[str]:
    candidates: list[str] = []

    explicit_url = _EXPLICIT_EXPORT_URLS[kind]
    if explicit_url:
        candidates.append(explicit_url)

    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(href=True):
        href = (element.get("href") or "").strip()
        if not href or href.startswith("javascript:"):
            continue
        lowered = href.lower()
        if any(token in lowered for token in ("xls", "xlsx", "download", "export")):
            candidates.append(urljoin(page_url, href))

    for match in re.findall(
        r"['\"]([^'\"]+(?:xlsx|xls)[^'\"]*)['\"]", html, flags=re.IGNORECASE
    ):
        candidates.append(urljoin(page_url, match))

    for suffix in _GENERIC_EXPORT_SUFFIXES:
        candidates.append(f"{page_url.rstrip('/')}/{suffix}")
        candidates.append(f"{page_url}?format={suffix}")
        candidates.append(f"{page_url}?download={suffix}")

    return _dedupe_urls(candidates)


def _build_page_url(kind: LeagueAssetKind) -> str:
    base_url = settings.fantacalcio_league_base_url.rstrip("/")
    slug = settings.fantacalcio_league_slug.strip("/")
    segment = _PAGE_SEGMENTS[kind]
    return f"{base_url}/{slug}/{segment}"


def _build_league_home_url() -> str:
    base_url = settings.fantacalcio_league_base_url.rstrip("/")
    slug = settings.fantacalcio_league_slug.strip("/")
    return f"{base_url}/{slug}"


def _fetch_text(url: str) -> str:
    with _client() as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _fetch_binary(url: str) -> bytes:
    with _client() as client:
        response = client.get(url)
        response.raise_for_status()
        content = response.content
        if not content:
            raise RemoteLeagueAssetError(f"Download remoto vuoto da {url}")
        return content


def _build_verify_config() -> bool | str | ssl.SSLContext:
    if not settings.fantacalcio_ssl_verify:
        return False

    if settings.fantacalcio_ca_bundle:
        return settings.fantacalcio_ca_bundle

    # Use the OS trust store instead of httpx/certifi defaults.
    # This is required on corporate Windows machines with custom root CAs,
    # and also works on Linux platforms like Railway through system CAs.
    return ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)


def _client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(
            connect=settings.connection_timeout,
            read=settings.read_timeout,
            write=settings.read_timeout,
            pool=settings.connection_timeout,
        ),
        verify=_build_verify_config(),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*;q=0.8",
        },
    )


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        clean_url = url.strip()
        if not clean_url or clean_url in seen:
            continue
        seen.add(clean_url)
        deduped.append(clean_url)
    return deduped


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_team_name(value: str) -> str:
    normalized = _clean_cell(value)
    # Public standings rows sometimes append an isolated score token to the
    # team label, e.g. "4 BIANCHI 0". Strip only the trailing integer token.
    return re.sub(r"\s+-?\d+$", "", normalized).strip()


def _parse_optional_score(node) -> float | None:
    if node is None:
        return None
    text = _clean_cell(node.get_text(" ", strip=True))
    if not text or not _looks_like_number(text):
        return None
    return float(_parse_number(text))


def _looks_like_int(value: str) -> bool:
    return re.fullmatch(r"-?\d+", value.replace(".", "").strip()) is not None


def _looks_like_number(value: str) -> bool:
    return re.fullmatch(r"-?\d+(?:[.,]\d+)?", value.replace(" ", "")) is not None


def _parse_number(value: str) -> float:
    return float(value.replace(".", "").replace(",", ".").strip())
