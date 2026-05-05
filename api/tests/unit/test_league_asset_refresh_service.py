import pytest

from app.services.league_asset_refresh_service import (
    RemoteLeagueAssetError,
    parse_latest_calendar_round_html,
    parse_standings_html,
    refresh_remote_league_asset,
)

STANDINGS_HTML = """
<html>
  <body>
    <table class="ranking">
      <tr>
        <th>#</th><th></th><th>Squadra</th><th>G</th><th>V</th><th>N</th><th>P</th><th>GF</th><th>GS</th><th>DR</th><th>Pt</th><th>Tot</th>
      </tr>
      <tr>
        <td>1</td><td></td><td>4 BIANCHI</td><td>33</td><td>14</td><td>9</td><td>10</td><td>55</td><td>44</td><td>11</td><td>51</td><td>2363,00</td>
      </tr>
      <tr>
        <td>2</td><td></td><td>CELL-TIC</td><td>33</td><td>14</td><td>9</td><td>10</td><td>53</td><td>44</td><td>9</td><td>51</td><td>2349,00</td>
      </tr>
    </table>
  </body>
</html>
"""

CALENDAR_HTML = """
<html>
  <body>
    <div class="widget widget-bordered match-results versus group-results">
      <header class="widget-header clearfix">
        <h4 class="widget-title">Ultima Giornata (33a Euro Lega - 35a Serie A)</h4>
      </header>
      <ul class="widget-body box raised versus">
        <li class="list-group-item match match-result row highlight">
          <div class="team team-home col-xs-6">
            <h5 class="team-name">4 BIANCHI</h5>
            <div class="team-score">2</div>
          </div>
          <div class="team team-away col-xs-6">
            <h5 class="team-name">CELL-TIC</h5>
            <div class="team-score">2</div>
          </div>
        </li>
        <li class="list-group-item match match-result row highlight">
          <div class="team team-home col-xs-6">
            <h5 class="team-name">NIGERIA TEAM</h5>
            <div class="team-score">1</div>
          </div>
          <div class="team team-away col-xs-6">
            <h5 class="team-name">DIO KEAN</h5>
            <div class="team-score">0</div>
          </div>
        </li>
      </ul>
    </div>
  </body>
</html>
"""


def test_parse_standings_html_extracts_rows():
    rows = parse_standings_html(STANDINGS_HTML)

    assert len(rows) == 2
    assert rows[0]["position"] == 1
    assert rows[0]["team_name"] == "4 BIANCHI"
    assert rows[0]["points"] == 51
    assert rows[0]["total_points"] == 2363.0


def test_refresh_remote_classifica_falls_back_to_html(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.services.league_asset_refresh_service._fetch_text",
        lambda _url: STANDINGS_HTML,
    )
    monkeypatch.setattr(
        "app.services.league_asset_refresh_service._iter_candidate_urls",
        lambda *_args: [],
    )

    result = refresh_remote_league_asset("classifica")

    assert result.source_kind == "html"
    assert result.source_url.endswith("/classifica")
    assert len(result.imported_rows) == 2
    assert result.imported_rows[1]["team_name"] == "CELL-TIC"


def test_parse_latest_calendar_round_html_extracts_round_and_matches():
    rounds = parse_latest_calendar_round_html(CALENDAR_HTML)

    assert len(rounds) == 1
    assert rounds[0]["league_round"] == 33
    assert rounds[0]["serie_a_round"] == 35
    assert len(rounds[0]["matches"]) == 2
    assert rounds[0]["matches"][0]["home_team"] == "4 BIANCHI"
    assert rounds[0]["matches"][0]["result"] == "2-2"


def test_refresh_remote_calendar_falls_back_to_latest_round_html(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "app.services.league_asset_refresh_service._fetch_text",
        lambda _url: CALENDAR_HTML,
    )

    result = refresh_remote_league_asset("calendar")

    assert result.source_kind == "html"
    assert result.source_url.endswith("/cena-maskia-championship")
    assert result.imported_rows[0]["league_round"] == 33


def test_refresh_remote_rose_requires_excel(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(
        RemoteLeagueAssetError,
        match="solo tramite upload Excel",
    ):
        refresh_remote_league_asset("rose")
