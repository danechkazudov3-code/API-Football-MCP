"""Pure utilities for pricing and ranking forecast candidates.

This module deliberately does not estimate match probabilities. It evaluates
probabilities supplied by a separately implemented and validated model.
"""

from __future__ import annotations

from typing import Any


def evaluate_candidate(
    candidate: dict[str, Any],
    *,
    model_validated: bool = False,
    min_expected_value: float = 0.03,
    min_probability: float = 0.0,
) -> dict[str, Any]:
    """Calculate pricing metrics and assign a visible recommendation status.

    Required candidate inputs: market, selection, odds. Probability may be
    omitted; in that case no fair odds or EV are fabricated.
    """
    result = dict(candidate)
    result.setdefault("status", "INSUFFICIENT_DATA")
    result.setdefault("reasons", [])

    try:
        odds = float(result.get("odds"))
    except (TypeError, ValueError):
        odds = 0.0

    if odds <= 1.0:
        result.update({
            "status": "INSUFFICIENT_DATA",
            "fair_odds": None,
            "implied_probability": None,
            "expected_value": None,
            "reasons": ["Missing or invalid decimal odds (must be > 1.0)."],
        })
        return result

    result["implied_probability"] = round(1.0 / odds, 6)

    probability = result.get("model_probability")
    if probability is None:
        result.update({
            "status": "INSUFFICIENT_DATA",
            "fair_odds": None,
            "expected_value": None,
            "reasons": ["No supported model probability is available."],
        })
        return result

    try:
        probability = float(probability)
    except (TypeError, ValueError):
        probability = -1.0

    if not 0.0 < probability < 1.0:
        result.update({
            "status": "INSUFFICIENT_DATA",
            "fair_odds": None,
            "expected_value": None,
            "reasons": ["Model probability must be between 0 and 1."],
        })
        return result

    result["model_probability"] = probability
    result["fair_odds"] = round(1.0 / probability, 4)
    result["expected_value"] = round(probability * odds - 1.0, 6)

    # The preferred coefficient band is a ranking preference, not a hard filter.
    # Longshots and short-priced favourites remain visible for transparency.
    if 1.65 <= odds <= 2.50:
        result["odds_profile"] = "PREFERRED"
    elif odds < 1.65:
        result["odds_profile"] = "LOW_ODDS"
    else:
        result["odds_profile"] = "HIGH_VARIANCE"

    lower_bound = result.get("probability_lower_bound")
    reasons: list[str] = []

    if result["expected_value"] < 0:
        status = "NO_BET"
        reasons.append("Current odds are below the model break-even price.")
    elif not model_validated:
        status = "LEAN"
        reasons.append("Positive point-estimate EV, but the model is not validated.")
    elif lower_bound is None:
        status = "LEAN"
        reasons.append("Uncertainty bound is unavailable; VALUE_BET is not permitted.")
    else:
        try:
            lower_bound = float(lower_bound)
        except (TypeError, ValueError):
            lower_bound = -1.0

        conservative_ev = lower_bound * odds - 1.0
        result["conservative_expected_value"] = round(conservative_ev, 6)
        if lower_bound < min_probability:
            status = "LEAN"
            reasons.append("Conservative probability is below the configured minimum.")
        elif conservative_ev >= min_expected_value:
            status = "VALUE_BET"
            reasons.append("Validated conservative EV clears the configured threshold.")
        else:
            status = "WATCHLIST"
            reasons.append("Point estimate is positive, but conservative EV misses the threshold.")

    result["status"] = status
    result["reasons"] = reasons
    return result


def select_primary_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-ranked visible candidate; never filter by VALUE status."""
    if not candidates:
        return None

    rank = {
        "VALUE_BET": 0,
        "LEAN": 1,
        "WATCHLIST": 2,
        "NO_BET": 3,
        "INSUFFICIENT_DATA": 4,
    }

    def key(candidate: dict[str, Any]) -> tuple[float, float, float, float]:
        status_rank = rank.get(candidate.get("status"), 5)
        odds_profile_rank = {
            "PREFERRED": 0,
            "LOW_ODDS": 1,
            "HIGH_VARIANCE": 2,
            None: 3,
        }.get(candidate.get("odds_profile"), 3)
        ev = candidate.get("conservative_expected_value")
        if ev is None:
            ev = candidate.get("expected_value")
        try:
            ev_score = float(ev)
        except (TypeError, ValueError):
            ev_score = float("-inf")
        try:
            probability_score = float(candidate.get("model_probability"))
        except (TypeError, ValueError):
            probability_score = float("-inf")
        return status_rank, odds_profile_rank, -ev_score, -probability_score

    return min(candidates, key=key)
