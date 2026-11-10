"""Pure utilities for pricing and ranking forecast candidates.

This module does not estimate match probabilities. It evaluates probabilities
supplied by a separately implemented model.
"""
from __future__ import annotations
from typing import Any


def evaluate_candidate(
    candidate: dict[str, Any],
    *,
    model_validated: bool = False,
    min_expected_value: float = 0.03,
    min_probability: float = 0.0,
    min_edge: float = 0.0,
) -> dict[str, Any]:
    """Calculate pricing metrics and assign a visible recommendation status."""
    result = dict(candidate)
    result.setdefault("status", "INSUFFICIENT_DATA")
    try:
        odds = float(result.get("odds"))
    except (TypeError, ValueError):
        odds = 0.0

    if odds <= 1.0:
        result.update({
            "status": "INSUFFICIENT_DATA", "fair_odds": None,
            "implied_probability": None, "expected_value": None, "edge": None,
            "reasons": ["Missing or invalid decimal odds (must be > 1.0)."],
        })
        return result

    result["implied_probability"] = round(1.0 / odds, 6)
    if 1.50 <= odds <= 2.50:
        result["odds_profile"] = "PREFERRED"
    elif odds < 1.50:
        result["odds_profile"] = "LOW_ODDS"
    else:
        result["odds_profile"] = "HIGH_VARIANCE"

    try:
        probability = float(result.get("model_probability"))
    except (TypeError, ValueError):
        probability = -1.0
    if not 0.0 < probability < 1.0:
        result.update({
            "status": "INSUFFICIENT_DATA", "fair_odds": None,
            "expected_value": None, "edge": None,
            "reasons": ["No valid supported model probability is available."],
        })
        return result

    result["model_probability"] = probability
    result["fair_odds"] = round(1.0 / probability, 4)
    result["expected_value"] = round(probability * odds - 1.0, 6)

    try:
        no_vig_probability = float(result.get("no_vig_probability"))
    except (TypeError, ValueError):
        no_vig_probability = -1.0
    result["edge"] = (
        round(probability - no_vig_probability, 6)
        if 0.0 < no_vig_probability < 1.0 else None
    )

    if result["expected_value"] < 0:
        status = "NO_BET"
        reasons = ["Current odds are below the model break-even price."]
    elif result["edge"] is None:
        status = "INSUFFICIENT_DATA"
        reasons = ["A complete same-bookmaker market is required to calculate no-vig edge."]
    elif result["edge"] <= min_edge:
        status = "NO_BET"
        reasons = ["Model edge does not exceed the configured minimum."]
    elif not model_validated:
        status = "LEAN"
        reasons = ["Positive EV and edge, but the model is not validated."]
    else:
        lower_bound = result.get("probability_lower_bound")
        try:
            lower_bound = float(lower_bound)
        except (TypeError, ValueError):
            lower_bound = None
        if lower_bound is None or not 0 < lower_bound < 1:
            status = "LEAN"
            reasons = ["Uncertainty bound is unavailable; VALUE_BET is not permitted."]
        else:
            conservative_ev = lower_bound * odds - 1.0
            conservative_edge = lower_bound - no_vig_probability
            result["conservative_expected_value"] = round(conservative_ev, 6)
            result["conservative_edge"] = round(conservative_edge, 6)
            if lower_bound < min_probability:
                status = "LEAN"
                reasons = ["Conservative probability is below the configured minimum."]
            elif conservative_edge <= min_edge:
                status = "WATCHLIST"
                reasons = ["Conservative edge does not exceed the configured minimum."]
            elif conservative_ev >= min_expected_value:
                status = "VALUE_BET"
                reasons = ["Validated conservative EV and edge clear configured thresholds."]
            else:
                status = "WATCHLIST"
                reasons = ["Point estimate is positive, but conservative EV misses the threshold."]

    result["status"] = status
    result["reasons"] = reasons
    return result


def select_primary_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-ranked visible candidate; never filter by VALUE status."""
    if not candidates:
        return None
    rank = {"VALUE_BET": 0, "LEAN": 1, "WATCHLIST": 2, "NO_BET": 3, "INSUFFICIENT_DATA": 4}

    def key(candidate: dict[str, Any]) -> tuple[float, float, float]:
        status_rank = rank.get(candidate.get("status"), 5)
        ev = candidate.get("conservative_expected_value", candidate.get("expected_value"))
        try:
            ev_score = float(ev)
        except (TypeError, ValueError):
            ev_score = float("-inf")
        try:
            probability_score = float(candidate.get("model_probability"))
        except (TypeError, ValueError):
            probability_score = float("-inf")
        return status_rank, -ev_score, -probability_score

    return min(candidates, key=key)
