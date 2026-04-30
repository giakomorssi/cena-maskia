"""Shared roster finance rules: cost band, amortization, and fixed salary."""

from __future__ import annotations

from typing import Any

FASCIA_RULES = (
    {
        "key": "1_9",
        "label": "1-9",
        "min": 1.0,
        "max": 9.0,
        "amm_pct": 1.0,
        "salary": 0.5,
    },
    {
        "key": "10_19",
        "label": "10-19",
        "min": 10.0,
        "max": 19.0,
        "amm_pct": 0.95,
        "salary": 1.0,
    },
    {
        "key": "20_34",
        "label": "20-34",
        "min": 20.0,
        "max": 34.0,
        "amm_pct": 0.9,
        "salary": 2.0,
    },
    {
        "key": "35_49",
        "label": "35-49",
        "min": 35.0,
        "max": 49.0,
        "amm_pct": 0.85,
        "salary": 3.0,
    },
    {
        "key": "50_69",
        "label": "50-69",
        "min": 50.0,
        "max": 69.0,
        "amm_pct": 0.75,
        "salary": 4.5,
    },
    {
        "key": "70_89",
        "label": "70-89",
        "min": 70.0,
        "max": 89.0,
        "amm_pct": 0.65,
        "salary": 6.0,
    },
    {
        "key": "90_120",
        "label": "90-120",
        "min": 90.0,
        "max": 120.0,
        "amm_pct": 0.6,
        "salary": 8.0,
    },
    {
        "key": "120_plus",
        "label": "120+",
        "min": 121.0,
        "max": None,
        "amm_pct": 0.6,
        "salary": 10.0,
    },
)

LEGACY_FASCIA_AMMORTIZATION = {
    "1_19": 1.0,
    "20_59": 0.6,
    "60_plus": 0.6,
}


def _to_cost(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def rule_for_cost(cost: float) -> dict[str, Any]:
    numeric_cost = _to_cost(cost)
    for rule in FASCIA_RULES:
        max_value = rule["max"]
        if numeric_cost >= float(rule["min"]) and (
            max_value is None or numeric_cost <= float(max_value)
        ):
            return rule
    return FASCIA_RULES[0]


def fascia_from_cost(cost: float) -> str:
    return str(rule_for_cost(cost)["key"])


def salary_from_cost(cost: float) -> float:
    return float(rule_for_cost(cost)["salary"])


def amortization_pct_from_cost(cost: float) -> float:
    return float(rule_for_cost(cost)["amm_pct"])


def amortization_pct_from_fascia(fascia: str) -> float:
    normalized = (fascia or "").strip().lower().replace(" ", "")
    for rule in FASCIA_RULES:
        if normalized in {rule["label"].replace("-", "_"), rule["key"], rule["label"]}:
            return float(rule["amm_pct"])
    if normalized in LEGACY_FASCIA_AMMORTIZATION:
        return float(LEGACY_FASCIA_AMMORTIZATION[normalized])
    try:
        return amortization_pct_from_cost(float(normalized))
    except ValueError:
        return float(FASCIA_RULES[0]["amm_pct"])


def normalize_player_financials(
    data: dict[str, Any], *, fallback_market_value: float | None = None
) -> dict[str, Any]:
    normalized = dict(data)
    if "market_value" in normalized:
        cost = _to_cost(normalized.get("market_value"))
        normalized["market_value"] = cost
    elif fallback_market_value is not None and (
        "salary" in normalized or "fascia" in normalized
    ):
        cost = _to_cost(fallback_market_value)
    else:
        return normalized

    normalized["fascia"] = fascia_from_cost(cost)
    normalized["salary"] = salary_from_cost(cost)
    return normalized
