from app.services.balance_service import amortization_pct
from app.services.player_finance_rules import (
    fascia_from_cost,
    normalize_player_financials,
    salary_from_cost,
)


def test_cost_rules_match_requested_bands():
    assert fascia_from_cost(9) == "1_9"
    assert salary_from_cost(9) == 0.5
    assert amortization_pct("1_9") == 1.0

    assert fascia_from_cost(19) == "10_19"
    assert salary_from_cost(19) == 1.0
    assert amortization_pct("10_19") == 0.95

    assert fascia_from_cost(34) == "20_34"
    assert salary_from_cost(34) == 2.0
    assert amortization_pct("20_34") == 0.9

    assert fascia_from_cost(49) == "35_49"
    assert salary_from_cost(49) == 3.0
    assert amortization_pct("35_49") == 0.85

    assert fascia_from_cost(69) == "50_69"
    assert salary_from_cost(69) == 4.5
    assert amortization_pct("50_69") == 0.75

    assert fascia_from_cost(89) == "70_89"
    assert salary_from_cost(89) == 6.0
    assert amortization_pct("70_89") == 0.65

    assert fascia_from_cost(120) == "90_120"
    assert salary_from_cost(120) == 8.0
    assert amortization_pct("90_120") == 0.6

    assert fascia_from_cost(121) == "120_plus"
    assert salary_from_cost(121) == 10.0
    assert amortization_pct("120_plus") == 0.6


def test_normalize_player_financials_derives_salary_and_fascia_from_cost():
    normalized = normalize_player_financials(
        {"market_value": 52, "salary": 999, "fascia": "1_9"}
    )

    assert normalized["market_value"] == 52.0
    assert normalized["fascia"] == "50_69"
    assert normalized["salary"] == 4.5


def test_normalize_player_financials_uses_existing_cost_on_partial_update():
    normalized = normalize_player_financials({"salary": 999}, fallback_market_value=71)

    assert normalized["fascia"] == "70_89"
    assert normalized["salary"] == 6.0
