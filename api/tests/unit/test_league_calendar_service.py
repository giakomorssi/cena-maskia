from app.services.league_calendar_service import get_league_calendar_data


def test_league_calendar_data_parses_public_excels():
    data = get_league_calendar_data()

    assert data.standings
    assert data.rounds
    assert data.standings[0].team == "DIO KEAN"
    assert data.standings[0].points == 51
    assert data.rounds[0].league_round == 1
    assert data.rounds[0].serie_a_round == 3
    assert len(data.rounds[0].matches) == 5
    assert data.rounds[0].matches[0].home_team == "Montauto fc"
    assert data.rounds[0].matches[0].away_team == "DIO KEAN"
